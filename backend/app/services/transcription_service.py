import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from faster_whisper import WhisperModel
from sqlalchemy import delete, select

from app.config import get_settings
from app.database import SessionLocal
from app.models import Recording, TranscriptSegment

logger = logging.getLogger(__name__)
_model: WhisperModel | None = None
_model_lock = Lock()


@dataclass(frozen=True)
class TranscribedSegment:
    start: float
    end: float
    text: str


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                settings = get_settings()
                _model = WhisperModel(
                    settings.whisper_model,
                    device=settings.whisper_device,
                    compute_type=settings.whisper_compute_type,
                )
    return _model


def transcribe_audio(file_path: str) -> list[TranscribedSegment]:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")

    segments, _ = _get_model().transcribe(str(path), vad_filter=True)
    return [
        TranscribedSegment(
            start=float(segment.start),
            end=float(segment.end),
            text=segment.text.strip(),
        )
        for segment in segments
        if segment.text.strip()
    ]
def process_recording(recording_id: str) -> None:
    with SessionLocal() as db:
        recording = db.scalar(select(Recording).where(Recording.id == recording_id))
        if recording is None:
            logger.error("Cannot transcribe missing recording %s", recording_id)
            return
        if recording.status == "completed":
            return
        recording.status = "processing"
        db.commit()
        file_path = recording.file_path

    try:
        segments = transcribe_audio(file_path)
        with SessionLocal() as db:
            recording = db.scalar(select(Recording).where(Recording.id == recording_id))
            if recording is None:
                logger.error("Recording %s was deleted during transcription", recording_id)
                return
            db.execute(delete(TranscriptSegment).where(TranscriptSegment.recording_id == recording_id))
            recording.transcript_segments = [
                TranscriptSegment(
                    recording_id=recording_id,
                    start_time=segment.start,
                    end_time=segment.end,
                    text=segment.text,
                )
                for segment in segments
            ]
            recording.status = "completed"
            db.commit()
        from app.services.extraction_service import process_insights

        process_insights(recording_id)
    except Exception:
        logger.exception("Transcription failed for recording %s", recording_id)
        with SessionLocal() as db:
            recording = db.scalar(select(Recording).where(Recording.id == recording_id))
            if recording is not None:
                recording.status = "failed"
                db.commit()
