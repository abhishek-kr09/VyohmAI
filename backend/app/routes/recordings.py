from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
import json

from app.models import ActionItem, Recording, RecordingInsight, TranscriptSegment
from app.schemas import (
    ActionItemResponse,
    ExtractionResponse,
    InsightResponse,
    MeetingInsight,
    PersonInsight,
    RecordingDetailResponse,
    RecordingResponse,
    InsightSessionResponse,
    TranscriptSegmentResponse,
    TranscriptionResponse,
)
from app.services.extraction_service import process_insights
from app.services.transcription_service import process_recording

router = APIRouter(prefix="/recordings", tags=["recordings"])


@router.get("", response_model=list[RecordingResponse])
def list_recordings(db: Session = Depends(get_db)) -> list[Recording]:
    recordings = list(db.scalars(select(Recording).order_by(Recording.recorded_at.desc())))
    for recording in recordings:
        recording.transcript_count = db.scalar(
            select(func.count(TranscriptSegment.id)).where(TranscriptSegment.recording_id == recording.id)
        ) or 0
    return recordings


@router.get("/insights", response_model=list[InsightSessionResponse])
def list_insights(db: Session = Depends(get_db)) -> list[InsightSessionResponse]:
    recordings = list(db.scalars(select(Recording).order_by(Recording.recorded_at.desc())))
    sessions: list[InsightSessionResponse] = []
    for recording in recordings:
        insight = db.scalar(select(RecordingInsight).where(RecordingInsight.recording_id == recording.id))
        if insight is None:
            sessions.append(InsightSessionResponse(
                recording_id=recording.id,
                session_name=recording.filename,
                recorded_at=recording.recorded_at,
                duration_ms=recording.duration_ms,
                status=recording.status,
            ))
            continue
        sessions.append(InsightSessionResponse(
            recording_id=recording.id,
            session_name=recording.filename,
            recorded_at=recording.recorded_at,
            duration_ms=recording.duration_ms,
            status=recording.status,
            insight=InsightResponse(
                id=insight.id,
                recording_id=insight.recording_id,
                topic=insight.topic,
                summary=insight.summary,
                highlights=json.loads(insight.highlights or "[]"),
                people=[PersonInsight.model_validate(item) for item in json.loads(insight.people or "[]")],
                meetings=[MeetingInsight.model_validate(item) for item in json.loads(insight.meetings or "[]")],
                created_at=insight.created_at,
            ),
            action_items=[ActionItemResponse.model_validate(item) for item in db.scalars(
                select(ActionItem).where(ActionItem.recording_id == recording.id)
            )],
        ))
    return sessions


@router.get("/{recording_id}", response_model=RecordingDetailResponse)
def get_recording(recording_id: str, db: Session = Depends(get_db)) -> RecordingDetailResponse:
    recording = db.scalar(select(Recording).where(Recording.id == recording_id))
    if recording is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    segments = list(
        db.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.recording_id == recording_id)
            .order_by(TranscriptSegment.start_time)
        )
    )
    recording.transcript_count = len(segments)
    insight = db.scalar(select(RecordingInsight).where(RecordingInsight.recording_id == recording_id))
    actions = list(db.scalars(select(ActionItem).where(ActionItem.recording_id == recording_id)))
    insight_response = None
    if insight is not None:
        insight_response = InsightResponse(
            id=insight.id,
            recording_id=insight.recording_id,
            topic=insight.topic,
            summary=insight.summary,
            highlights=json.loads(insight.highlights or "[]"),
            people=[PersonInsight.model_validate(item) for item in json.loads(insight.people or "[]")],
            meetings=[MeetingInsight.model_validate(item) for item in json.loads(insight.meetings or "[]")],
            created_at=insight.created_at,
        )
    return RecordingDetailResponse(
        **RecordingResponse.model_validate(recording).model_dump(),
        transcript=[TranscriptSegmentResponse.model_validate(segment) for segment in segments],
        insight=insight_response,
        action_items=[ActionItemResponse.model_validate(item) for item in actions],
    )


@router.get("/{recording_id}/audio", response_class=FileResponse)
def get_audio(recording_id: str, db: Session = Depends(get_db)) -> FileResponse:
    recording = db.scalar(select(Recording).where(Recording.id == recording_id))
    if recording is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    audio_path = Path(recording.file_path)
    if not audio_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(audio_path, media_type="audio/wav", filename=recording.filename)


@router.get("/{recording_id}/transcript", response_model=TranscriptionResponse)
def get_transcript(recording_id: str, db: Session = Depends(get_db)) -> TranscriptionResponse:
    recording = db.scalar(select(Recording).where(Recording.id == recording_id))
    if recording is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    segments = list(
        db.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.recording_id == recording_id)
            .order_by(TranscriptSegment.start_time)
        )
    )
    return TranscriptionResponse(
        recording_id=recording_id,
        status=recording.status,
        segments=[TranscriptSegmentResponse.model_validate(segment) for segment in segments],
    )


@router.post(
    "/{recording_id}/transcribe",
    response_model=TranscriptionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_transcription(
    recording_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> TranscriptionResponse:
    recording = db.scalar(select(Recording).where(Recording.id == recording_id))
    if recording is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    if recording.status == "processing":
        raise HTTPException(status_code=409, detail="Transcription is already processing")
    if recording.status == "completed":
        raise HTTPException(status_code=409, detail="Transcription is already completed")

    recording.status = "processing"
    db.commit()
    background_tasks.add_task(process_recording, recording_id)
    return TranscriptionResponse(recording_id=recording_id, status="processing", segments=[])


@router.post("/{recording_id}/extract", response_model=ExtractionResponse, status_code=status.HTTP_202_ACCEPTED)
def extract_insights(
    recording_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ExtractionResponse:
    recording = db.scalar(select(Recording).where(Recording.id == recording_id))
    if recording is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    if recording.status != "completed":
        raise HTTPException(status_code=409, detail="Recording must have a completed transcript")
    background_tasks.add_task(process_insights, recording_id)
    return ExtractionResponse(recording_id=recording_id, status="processing")
