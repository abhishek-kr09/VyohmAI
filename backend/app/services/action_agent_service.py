import json
import re
from datetime import datetime, timedelta, timezone

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import ActionItem, CalendarEvent, EmailDraft, Recording, RecordingInsight

class AgentPlan(BaseModel):
    action_type: str = Field(pattern="^(create_calendar|create_email|complete_action|no_action)$")
    action_item_id: str | None = None
    title: str | None = None
    description: str | None = None
    recipient: str | None = None
    subject: str | None = None
    body: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    attendees: list[str] = Field(default_factory=list)


def _is_email(value: str) -> bool:
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip()) is not None


def _context(db, recording_id: str | None) -> str:
    query = select(ActionItem, Recording).join(Recording, Recording.id == ActionItem.recording_id).where(
        ActionItem.status != "completed"
    )
    if recording_id:
        query = query.where(ActionItem.recording_id == recording_id)
    rows = db.execute(query.order_by(ActionItem.due_date, Recording.recorded_at.desc())).all()
    actions = "\n".join(
        f"ID={item.id}; recording={recording.id}; person={item.person or 'unknown'}; "
        f"due={item.due_date or 'none'}; task={item.task}"
        for item, recording in rows
    ) or "No pending action items."

    session_query = select(Recording, RecordingInsight).join(
        RecordingInsight, RecordingInsight.recording_id == Recording.id
    )
    if recording_id:
        session_query = session_query.where(Recording.id == recording_id)
    sessions = db.execute(session_query.order_by(Recording.recorded_at.desc()).limit(5)).all()
    session_text = "\n".join(
        f"recording={recording.id}; name={recording.filename}; recorded_at={recording.recorded_at.isoformat()}; "
        f"topic={insight.topic or 'unknown'}; summary={insight.summary or 'none'}; "
        f"people={insight.people or '[]'}; meetings={insight.meetings or '[]'}"
        for recording, insight in sessions
    ) or "No session insights available."
    return f"Pending actions:\n{actions}\nSession insights:\n{session_text}"


def _plan(instruction: str, context: str) -> AgentPlan:
    settings = get_settings()
    if not settings.groq_api_key or not settings.llm_model:
        raise RuntimeError("GROQ_API_KEY and LLM_MODEL must be configured for agent actions")
    now = datetime.now(timezone.utc)
    prompt = (
        "You are the Pocket Recorder action agent. Convert the instruction into exactly one local action. "
        "Return only JSON matching the fields action_type, action_item_id, title, description, recipient, "
        "subject, body, start_time, end_time, attendees. action_type must be create_calendar, create_email, "
        "complete_action, or no_action. Use an existing action_item_id when completing a task. "
        "For calendar events, use ISO-8601 with timezone offset; resolve relative dates such as "
        "'Thursday' or 'tomorrow' against the session's recorded_at and keep its timezone offset; "
        "default duration is 30 minutes; put attendee email addresses only if they appear in the context. "
        "For follow-up emails, write a concise, professional body grounded only in the session "
        "summary and actions. If the recipient's email address is unknown, set recipient to the "
        "person's name; the user will correct it before saving. Never invent facts, dates, or email "
        "addresses. Use no_action only if the instruction cannot be mapped to any action. "
        f"Current UTC time: {now.isoformat()}\n{context}\nInstruction: {instruction}"
    )
    try:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={
                "model": settings.llm_model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": prompt}],
            },
            timeout=90,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise RuntimeError(
                "Groq authentication failed. Generate a new Groq API key and update GROQ_API_KEY."
            ) from exc
        raise RuntimeError(f"Agent request failed with HTTP {exc.response.status_code}") from exc
    except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Agent returned an unexpected response") from exc
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise RuntimeError("Agent returned no action plan")
    try:
        return AgentPlan.model_validate(json.loads(match.group(0)))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise RuntimeError("Agent returned an invalid action plan") from exc


def plan_action_item(action_item_id: str) -> tuple[AgentPlan, str]:
    with SessionLocal() as db:
        item = db.get(ActionItem, action_item_id)
        if item is None:
            raise LookupError("Action item not found")
        if item.status == "completed":
            raise ValueError("This action item is already completed")
        instruction = (
            f"Perform the pending action item with ID={item.id}: {item.task}."
            + (f" Responsible person: {item.person}." if item.person else "")
            + (f" Due: {item.due_date.isoformat()}." if item.due_date else "")
            + " Pick the single best action: create a calendar event if it involves scheduling a "
            "meeting or call with a known time, create an email draft if it requires contacting "
            "someone and an email address is known, otherwise mark this action item complete."
        )
        recording_id = item.recording_id
    return plan_instruction(instruction, recording_id), recording_id


def plan_instruction(instruction: str, recording_id: str | None) -> AgentPlan:
    with SessionLocal() as db:
        return _plan(instruction, _context(db, recording_id))


def execute_plan(plan: AgentPlan, recording_id: str | None) -> tuple[AgentPlan, object | None]:
    with SessionLocal() as db:
        if plan.action_type == "no_action":
            return plan, None
        if plan.action_type == "complete_action":
            item = db.get(ActionItem, plan.action_item_id) if plan.action_item_id else None
            if item is None or item.status == "completed":
                raise ValueError("The agent could not identify a pending action item to complete")
            item.status = "completed"
            db.commit()
            return plan, item
        if recording_id and db.get(Recording, recording_id) is None:
            raise ValueError("Source recording not found")
        if plan.action_type == "create_calendar":
            if not plan.title or not plan.start_time:
                raise ValueError("The agent needs a title and start time for a calendar event")
            if plan.start_time.tzinfo is None:
                raise ValueError("Calendar start time must include a timezone offset")
            end_time = plan.end_time or plan.start_time + timedelta(minutes=30)
            if end_time <= plan.start_time:
                raise ValueError("Calendar event end time must be after start time")
            if any(not _is_email(attendee) for attendee in plan.attendees):
                raise ValueError("Each attendee must be an email address")
            event = CalendarEvent(
                title=plan.title,
                description=plan.description,
                start_time=plan.start_time,
                end_time=end_time,
                attendees=",".join(plan.attendees) or None,
                source_recording_id=recording_id,
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            return plan, event
        if not plan.recipient or not plan.subject or not plan.body:
            raise ValueError("The agent needs a recipient, subject, and body for an email draft")
        if not _is_email(plan.recipient):
            raise ValueError("Enter the recipient's email address before saving the draft")
        draft = EmailDraft(
            recipient=plan.recipient,
            subject=plan.subject,
            body=plan.body,
            source_recording_id=recording_id,
            status="draft",
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return plan, draft


def describe_plan(plan: AgentPlan) -> str:
    if plan.action_type == "create_calendar":
        start = plan.start_time.isoformat() if plan.start_time else "unspecified time"
        return f"Create calendar event “{plan.title}” starting {start}."
    if plan.action_type == "create_email":
        return f"Save an email draft to {plan.recipient} with subject “{plan.subject}”. Nothing is sent."
    if plan.action_type == "complete_action":
        return "Mark the matching action item as complete."
    return "The agent did not find enough information to perform that action."


def execute_instruction(instruction: str, recording_id: str | None) -> tuple[AgentPlan, object | None]:
    return execute_plan(plan_instruction(instruction, recording_id), recording_id)
