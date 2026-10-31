import json
import logging
import re
from dataclasses import dataclass

import httpx
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import ActionItem, Recording, TranscriptSegment
from app.schemas import ChatEvidence

logger = logging.getLogger(__name__)

MAX_FULL_SESSION_SEGMENTS = 120


class ChatCompletion(BaseModel):
    answer: str = Field(min_length=1)
    citations: list[int] = Field(default_factory=list)


@dataclass(frozen=True)
class RetrievedEvidence:
    evidence: ChatEvidence
    source_text: str


def _session_documents(recording_id: str | None = None) -> list[Document]:
    with SessionLocal() as db:
        query = (
            select(TranscriptSegment, Recording)
            .join(Recording, Recording.id == TranscriptSegment.recording_id)
            .order_by(Recording.recorded_at.desc(), TranscriptSegment.start_time)
        )
        if recording_id:
            query = query.where(Recording.id == recording_id)
        rows = db.execute(query).all()
        documents = [
            Document(
                page_content=segment.text,
                metadata={
                    "recording_id": recording.id,
                    "recording_name": recording.filename,
                    "start_time": segment.start_time,
                    "end_time": segment.end_time,
                    "source_type": "transcript",
                },
            )
            for segment, recording in rows
        ]
        action_query = (
            select(ActionItem, Recording)
            .join(Recording, Recording.id == ActionItem.recording_id)
            .where(ActionItem.status != "completed")
        )
        if recording_id:
            action_query = action_query.where(ActionItem.recording_id == recording_id)
        for action, recording in db.execute(action_query).all():
            documents.append(
                Document(
                    page_content=f"Action item: {action.task}. Owner: {action.person or 'not specified'}.",
                    metadata={
                        "recording_id": recording.id,
                        "recording_name": recording.filename,
                        "start_time": 0.0,
                        "end_time": 0.0,
                        "source_type": "action_item",
                    },
                )
            )
    return documents


def retrieve_evidence(question: str, recording_id: str | None = None) -> list[RetrievedEvidence]:
    documents = _session_documents(recording_id)
    if not documents:
        return []
    if recording_id and len(documents) <= MAX_FULL_SESSION_SEGMENTS:
        transcript = [doc for doc in documents if doc.metadata["source_type"] == "transcript"]
        actions = [doc for doc in documents if doc.metadata["source_type"] != "transcript"]
        documents = transcript + actions
        return [
            RetrievedEvidence(
                evidence=ChatEvidence(
                    recording_id=document.metadata["recording_id"],
                    recording_name=document.metadata["recording_name"],
                    start_time=document.metadata["start_time"],
                    end_time=document.metadata["end_time"],
                    quote=document.page_content,
                ),
                source_text=document.page_content,
            )
            for document in documents
        ]
    retriever = BM25Retriever.from_documents(documents, k=min(12, len(documents)))
    retrieved_documents = retriever.invoke(question)
    return [
        RetrievedEvidence(
            evidence=ChatEvidence(
                recording_id=document.metadata["recording_id"],
                recording_name=document.metadata["recording_name"],
                start_time=document.metadata["start_time"],
                end_time=document.metadata["end_time"],
                quote=document.page_content,
            ),
            source_text=document.page_content,
        )
        for document in retrieved_documents
    ]


def _clean_answer(text: str) -> str:
    text = text.replace("\u202f", " ").replace("\u00a0", " ")
    text = re.sub(
        r"\s*[\(\[]\s*(?:segments?|evidence|seg\.?)\s*\d+(?:\s*[\u2013\u2014-]\s*\d+)?(?:\s*(?:,|and|&)\s*\d+)*\s*[\)\]]",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s*\[\d+(?:\s*,\s*\d+)*\]", "", text)
    text = text.replace("\u2011", "-").replace("\u2010", "-")
    text = re.sub(r"\(\s*\)", "", text)
    inline_items = re.split(r"\s*(?:^|(?<=[\s:;,]))\(?\d{1,2}[.)]\s+", text)
    if len(inline_items) >= 3 and "\n- " not in text:
        lead = inline_items[0].strip().rstrip(":;,")
        items = [
            re.sub(r"\s+(?:and|or)$", "", re.sub(r"^(?:and|or)\s+", "", item.strip(), flags=re.IGNORECASE).rstrip(";,. "), flags=re.IGNORECASE)
            for item in inline_items[1:]
        ]
        items = [item[:1].upper() + item[1:] for item in items if item]
        if lead:
            lead = lead + ":"
        items = [item.rstrip(";,. ") for item in items]
        return "\n".join(([lead] if lead else []) + [f"- {item}" for item in items]).strip()
    return text.strip()


def _bulletize(text: str) -> str:
    if "\n" in text.strip() or len(text) < 90:
        return text
    match = re.match(r"^(You (?:promised|committed|agreed|need|should|have)\b[^,:]*?\b(?:to)?)\s+(.+?)\.?$", text.strip(), flags=re.DOTALL)
    if not match:
        return text
    parts = [part.strip() for part in re.split(r",\s*(?:and\s+)?|\s+and\s+(?=[a-z]+\s)", match.group(2)) if part.strip()]
    if len(parts) < 3 or any(len(part) > 120 for part in parts):
        return text
    items = [re.sub(r"^(?:to\s+)?", "", part)[:1].upper() + re.sub(r"^(?:to\s+)?", "", part)[1:] for part in parts]
    return "\n".join([f"{match.group(1).rstrip()}:"] + [f"- {item}" for item in items])


def _parse_completion(content: str) -> ChatCompletion:
    match = re.search(r"\{.*\}", content.strip(), re.DOTALL)
    if not match:
        raise RuntimeError("LLM returned no JSON chat response")
    try:
        payload = json.loads(match.group(0))
        completion = ChatCompletion.model_validate(payload)
        completion.answer = _bulletize(_clean_answer(completion.answer)) or completion.answer
        return completion
    except (json.JSONDecodeError, ValidationError) as exc:
        raise RuntimeError("LLM returned invalid structured chat JSON") from exc


def _answer_from_llm(
    question: str,
    retrieved: list[RetrievedEvidence],
    retry: bool = False,
) -> ChatCompletion:
    settings = get_settings()
    if not settings.groq_api_key or not settings.llm_model:
        raise RuntimeError("GROQ_API_KEY and LLM_MODEL must be configured for chat")
    evidence_text = "\n".join(
        f"[{index}] {item.evidence.recording_name} "
        f"({item.evidence.start_time:.2f}-{item.evidence.end_time:.2f}s): "
        f"{item.source_text}"
        for index, item in enumerate(retrieved)
    )
    system_prompt = (
        "Answer only from the supplied evidence. Return only JSON with keys answer and citations. "
        "Citations must be a list of zero-based evidence indexes. Every factual claim must have at "
        "least one citation. If the evidence does not answer the question, say that the recordings "
        "do not contain enough evidence and use an empty citations list. Never invent speakers, "
        "names, dates, deadlines, or commitments. If any supplied evidence directly answers the "
        "question, you MUST include its zero-based index in citations. For broad questions such as "
        "'what was discussed', summarize the main points in the evidence and cite the segments "
        "that support them. The words meeting, session, conversation, call, and recording all refer "
        "to the recorded audio in the evidence, so do not refuse because the evidence is a call "
        "rather than a meeting. Only say the recordings lack evidence when the specific facts "
        "asked about (such as a price or date) are truly absent. "
        "Write the answer the way a helpful person would speak: start with one short, direct sentence "
        "that answers the question. Whenever the answer has three or more separate points (for example "
        "promises, tasks, topics, decisions, or reasons), you MUST follow the lead sentence with a "
        "bulleted list where each line starts with '- ' and holds one short point in plain language. Use at most one short "
        "closing sentence, and only if it adds something. Address the user as 'you' when they ask about "
        "their own words. Never write evidence numbers, segment numbers, timestamps, or brackets in the "
        "answer text; citations belong only in the citations list. Do not use markdown headings or tables. "
        "Do not number items inline like '1) ... 2) ...' and do not quote the transcript verbatim "
        "unless asked; paraphrase. Example of the required answer format, written as a JSON string: "
        "\"Here is what you committed to:\\n- Talk to John today about his situation\\n- Help the family "
        "with childcare\\n- Look for free or low-cost community resources\""
    )
    if retry:
        system_prompt += (
            " This is a citation correction attempt: review the evidence again and do not return "
            "an empty citations list when it contains a direct answer."
        )
    payload = {
        "model": settings.llm_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Question: {question}\nEvidence:\n{evidence_text}"},
        ],
    }
    try:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise RuntimeError(
                "Groq authentication failed. Generate a new Groq API key and update GROQ_API_KEY."
            ) from exc
        raise RuntimeError(f"Groq request failed with HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Could not reach Groq: {exc}") from exc
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Groq returned an unexpected chat response") from exc
    if not isinstance(content, str):
        raise RuntimeError("Groq returned non-text chat content")
    return _parse_completion(content)


def answer_question(question: str, recording_id: str | None = None) -> tuple[str, list[ChatEvidence]]:
    retrieved = retrieve_evidence(question, recording_id=recording_id)
    if not retrieved:
        return (
            "I could not find enough evidence in your recordings to answer that question; "
            "the recordings do not provide enough evidence.",
            [],
        )
    completion = _answer_from_llm(question, retrieved)
    valid_indexes = [
        index for index in completion.citations
        if 0 <= index < len(retrieved)
    ]
    if not valid_indexes:
        completion = _answer_from_llm(question, retrieved, retry=True)
        valid_indexes = [
            index for index in completion.citations
            if 0 <= index < len(retrieved)
        ]
    if not valid_indexes:
        return (
            "I found related transcript content, but it does not provide enough evidence "
            "to answer that question.",
            [],
        )
    return completion.answer, [retrieved[index].evidence for index in dict.fromkeys(valid_indexes)]
