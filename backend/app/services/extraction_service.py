import json
import logging
import re
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import delete, select

from app.config import get_settings
from app.database import SessionLocal
from app.models import ActionItem, Recording, RecordingInsight

logger = logging.getLogger(__name__)


class ExtractedAction(BaseModel):
    person: str | None = None
    task: str = Field(min_length=1)
    due_date: str | None = None


class ExtractedInsight(BaseModel):
    topic: str | None = None
    summary: str | None = None
    highlights: list[str] = Field(default_factory=list)
    people: list[dict[str, Any]] = Field(default_factory=list)
    meetings: list[dict[str, Any]] = Field(default_factory=list)
    action_items: list[ExtractedAction] = Field(default_factory=list)


def _parse_insight_content(content: str) -> ExtractedInsight:
    content = content.strip()
    fenced_json = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL | re.IGNORECASE)
    if fenced_json:
        content = fenced_json.group(1)
    else:
        json_start = content.find("{")
        json_end = content.rfind("}")
        if json_start >= 0 and json_end > json_start:
            content = content[json_start : json_end + 1]
    try:
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise RuntimeError("LLM insight response must be a JSON object")
        for field in ("people", "meetings", "action_items"):
            if isinstance(payload.get(field), dict):
                payload[field] = [payload[field]]
            elif payload.get(field) is None:
                payload[field] = []
        if isinstance(payload.get("highlights"), str):
            payload["highlights"] = [payload["highlights"]]
        elif payload.get("highlights") is None:
            payload["highlights"] = []
        payload["highlights"] = [
            item if isinstance(item, str) else str(item.get("text", item.get("highlight", "")))
            for item in payload.get("highlights", [])
            if isinstance(item, str) or isinstance(item, dict)
        ]
        payload["people"] = [
            {"name": item} if isinstance(item, str) else item
            for item in payload.get("people", [])
        ]
        payload["meetings"] = [
            {"purpose": item} if isinstance(item, str) else item
            for item in payload.get("meetings", [])
        ]
        normalized_actions = []
        for item in payload.get("action_items", []):
            if not isinstance(item, dict):
                continue
            normalized_actions.append({
                "person": item.get("person", item.get("responsible_person")),
                "task": item.get("task", item.get("description", "")),
                "due_date": item.get("due_date", item.get("deadline")),
            })
        payload["action_items"] = normalized_actions
        return ExtractedInsight.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        if isinstance(exc, ValidationError):
            logger.warning("LLM insight schema validation failed: %s", exc.errors())
        raise RuntimeError("LLM returned invalid structured insight JSON") from exc


def _transcript_text(recording_id: str) -> str:
    with SessionLocal() as db:
        recording = db.scalar(select(Recording).where(Recording.id == recording_id))
        if recording is None:
            raise ValueError("Recording not found")
        return "\n".join(
            f"[{segment.start_time:.2f}-{segment.end_time:.2f}] {segment.text}"
            for segment in sorted(recording.transcript_segments, key=lambda item: item.start_time)
        )


def _extract_from_llm(transcript: str) -> ExtractedInsight:
    settings = get_settings()
    if not settings.groq_api_key or not settings.llm_model:
        raise RuntimeError("GROQ_API_KEY and LLM_MODEL must be configured for insight extraction")
    system_prompt = (
        "You extract meeting information from transcripts. Return only valid JSON with keys "
        "topic, summary, highlights, people, meetings, action_items. Use null or [] when information is absent. "
        "Never invent names, dates, roles, deadlines, or commitments. Preserve uncertainty."
    )
    payload = {
        "model": settings.llm_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Transcript:\n{transcript}"},
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
        detail = exc.response.text[:300]
        raise RuntimeError(
            f"Groq request failed with HTTP {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Could not reach Groq: {exc}") from exc
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Groq returned an unexpected completion response") from exc
    if not isinstance(content, str):
        raise RuntimeError("Groq returned non-text insight content")

    return _parse_insight_content(content)


def process_insights(recording_id: str) -> None:
    try:
        extracted = _extract_from_llm(_transcript_text(recording_id))
        with SessionLocal() as db:
            recording = db.scalar(select(Recording).where(Recording.id == recording_id))
            if recording is None:
                raise ValueError("Recording not found")
            insight = db.scalar(select(RecordingInsight).where(RecordingInsight.recording_id == recording_id))
            if insight is None:
                insight = RecordingInsight(recording_id=recording_id)
                db.add(insight)
            insight.topic = extracted.topic
            insight.summary = extracted.summary
            insight.highlights = json.dumps(extracted.highlights)
            insight.people = json.dumps(extracted.people)
            insight.meetings = json.dumps(extracted.meetings)
            db.execute(delete(ActionItem).where(ActionItem.recording_id == recording_id))
            for item in extracted.action_items:
                due_date = datetime.fromisoformat(item.due_date) if item.due_date else None
                db.add(ActionItem(
                    recording_id=recording_id,
                    person=item.person,
                    task=item.task,
                    due_date=due_date,
                    status="pending",
                ))
            db.commit()
    except Exception as exc:
        logger.error("Insight extraction failed for recording %s: %s", recording_id, exc)
