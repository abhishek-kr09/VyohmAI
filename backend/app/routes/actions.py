from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActionItem, CalendarEvent, EmailDraft, Recording
from app.services.action_agent_service import execute_instruction
from app.schemas import (
    AgentActionResponse,
    AgentInstructionRequest,
    CalendarEventInput,
    CalendarEventResponse,
    DailyActionResponse,
    EmailDraftInput,
    EmailDraftResponse,
)

router = APIRouter(prefix="/actions", tags=["actions"])


@router.post("/agent", response_model=AgentActionResponse)
def run_agent(data: AgentInstructionRequest) -> AgentActionResponse:
    try:
        plan, result = execute_instruction(data.instruction, data.recording_id)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if plan.action_type == "create_calendar":
        return AgentActionResponse(
            message="Agent created a local calendar event.",
            action_type=plan.action_type,
            calendar_event=_event_response(result),
        )
    if plan.action_type == "create_email":
        return AgentActionResponse(
            message="Agent saved an email draft for review.",
            action_type=plan.action_type,
            email_draft=result,
        )
    if plan.action_type == "complete_action":
        return AgentActionResponse(
            message="Agent marked the action complete.",
            action_type=plan.action_type,
            action_item_id=result.id,
        )
    return AgentActionResponse(
        message="The agent did not find enough information to perform that action.",
        action_type=plan.action_type,
    )


@router.get("/daily", response_model=list[DailyActionResponse])
def list_daily_actions(db: Session = Depends(get_db)) -> list[DailyActionResponse]:
    rows = db.execute(
        select(ActionItem, Recording)
        .join(Recording, Recording.id == ActionItem.recording_id)
        .where(ActionItem.status != "completed")
        .order_by(ActionItem.due_date.is_(None), ActionItem.due_date, Recording.recorded_at.desc())
    ).all()
    return [
        DailyActionResponse(
            id=item.id,
            person=item.person,
            task=item.task,
            due_date=item.due_date,
            status=item.status,
            recording_name=recording.filename,
            recorded_at=recording.recorded_at,
        )
        for item, recording in rows
    ]


def _validate_event(data: CalendarEventInput, db: Session) -> None:
    if data.end_time <= data.start_time:
        raise HTTPException(status_code=422, detail="Calendar event end_time must be after start_time")
    if data.source_recording_id and db.get(Recording, data.source_recording_id) is None:
        raise HTTPException(status_code=404, detail="Source recording not found")
    if any("@" not in attendee or attendee.startswith("@") for attendee in data.attendees):
        raise HTTPException(status_code=422, detail="Each attendee must be an email address")


def _validate_draft(data: EmailDraftInput, db: Session) -> None:
    if "@" not in data.recipient or data.recipient.startswith("@"):
        raise HTTPException(status_code=422, detail="Recipient must be an email address")
    if data.source_recording_id and db.get(Recording, data.source_recording_id) is None:
        raise HTTPException(status_code=404, detail="Source recording not found")


def _event_response(event: CalendarEvent) -> CalendarEventResponse:
    return CalendarEventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        start_time=event.start_time,
        end_time=event.end_time,
        attendees=[item for item in (event.attendees or "").split(",") if item],
        source_recording_id=event.source_recording_id,
        created_at=event.created_at,
    )


@router.get("/calendar-events", response_model=list[CalendarEventResponse])
def list_calendar_events(db: Session = Depends(get_db)) -> list[CalendarEventResponse]:
    events = list(db.scalars(select(CalendarEvent).order_by(CalendarEvent.start_time)))
    return [_event_response(event) for event in events]


@router.post("/calendar-events/preview", response_model=CalendarEventInput)
def preview_calendar_event(data: CalendarEventInput, db: Session = Depends(get_db)) -> CalendarEventInput:
    _validate_event(data, db)
    return data


@router.post(
    "/calendar-events",
    response_model=CalendarEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_calendar_event(
    data: CalendarEventInput,
    confirmed: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> CalendarEventResponse:
    _validate_event(data, db)
    if not confirmed:
        raise HTTPException(
            status_code=409,
            detail="Confirmation is required before creating a calendar event",
        )
    event = CalendarEvent(
        title=data.title,
        description=data.description,
        start_time=data.start_time,
        end_time=data.end_time,
        attendees=",".join(data.attendees) or None,
        source_recording_id=data.source_recording_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return _event_response(event)


@router.get("/email-drafts", response_model=list[EmailDraftResponse])
def list_email_drafts(db: Session = Depends(get_db)) -> list[EmailDraft]:
    return list(db.scalars(select(EmailDraft).order_by(EmailDraft.created_at.desc())))


@router.post("/email-drafts/preview", response_model=EmailDraftInput)
def preview_email_draft(data: EmailDraftInput, db: Session = Depends(get_db)) -> EmailDraftInput:
    _validate_draft(data, db)
    return data


@router.post(
    "/email-drafts",
    response_model=EmailDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_email_draft(
    data: EmailDraftInput,
    confirmed: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> EmailDraft:
    _validate_draft(data, db)
    if not confirmed:
        raise HTTPException(
            status_code=409,
            detail="Confirmation is required before creating an email draft",
        )
    draft = EmailDraft(
        recipient=data.recipient,
        subject=data.subject,
        body=data.body,
        source_recording_id=data.source_recording_id,
        status="draft",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft
