import json
import re
from datetime import datetime, timedelta, timezone

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import ActionItem, CalendarEvent, EmailDraft, Recording

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


def _context(db, recording_id: str | None) -> str:
    query = select(ActionItem, Recording).join(Recording, Recording.id == ActionItem.recording_id).where(
        ActionItem.status != "completed"
    )
    if recording_id:
        query = query.where(ActionItem.recording_id == recording_id)
    rows = db.execute(query.order_by(ActionItem.due_date, Recording.recorded_at.desc())).all()
    return "\n".join(
        f"ID={item.id}; recording={recording.id}; person={item.person or 'unknown'}; "
        f"due={item.due_date or 'none'}; task={item.task}"
        for item, recording in rows
    ) or "No pending action items."


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
        "For calendar times use ISO-8601 with timezone; default duration is 30 minutes. Never invent an "
        "email address or attendee; use no_action if required information is absent. "
        f"Current UTC time: {now.isoformat()}\nPending actions:\n{context}\nInstruction: {instruction}"
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


def execute_instruction(instruction: str, recording_id: str | None) -> tuple[AgentPlan, object | None]:
    with SessionLocal() as db:
        plan = _plan(instruction, _context(db, recording_id))
        if plan.action_type == "no_action":
            return plan, None
        if plan.action_type == "complete_action":
            item = db.get(ActionItem, plan.action_item_id) if plan.action_item_id else None
            if item is None or item.status == "completed":
                raise ValueError("The agent could not identify a pending action item to complete")
            item.status = "completed"
            db.commit()
            return plan, item
        if plan.action_type == "create_calendar":
            if not plan.title or not plan.start_time:
                raise ValueError("The agent needs a title and start time for a calendar event")
            event = CalendarEvent(
                title=plan.title,
                description=plan.description,
                start_time=plan.start_time,
                end_time=plan.end_time or plan.start_time + timedelta(minutes=30),
                attendees=",".join(plan.attendees) or None,
                source_recording_id=recording_id,
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            return plan, event
        if not plan.recipient or not plan.subject or not plan.body:
            raise ValueError("The agent needs a recipient, subject, and body for an email draft")
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
