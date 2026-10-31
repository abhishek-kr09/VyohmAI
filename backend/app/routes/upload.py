import hashlib
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Recording
from app.schemas import UploadResponse
from app.services.transcription_service import process_recording

router = APIRouter(tags=["uploads"])
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def _validate_metadata(
    device_id: str, recorded_at: datetime, duration_ms: int, battery_pct: int | None
) -> None:
    if not device_id.strip() or len(device_id) > 120:
        raise HTTPException(status_code=422, detail="device_id must be 1-120 characters")
    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail="recorded_at must include a timezone offset")
    if duration_ms <= 0:
        raise HTTPException(status_code=422, detail="duration_ms must be greater than zero")
    if battery_pct is not None and not 0 <= battery_pct <= 100:
        raise HTTPException(status_code=422, detail="battery_pct must be between 0 and 100")


async def _read_wav(audio: UploadFile) -> tuple[bytes, str]:
    original_name = Path(audio.filename or "").name
    if not original_name or Path(original_name).suffix.lower() != ".wav":
        raise HTTPException(status_code=415, detail="audio must be a WAV file")
    if audio.content_type not in {"audio/wav", "audio/x-wav", "audio/wave", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="audio must use a WAV-compatible content type")

    data = await audio.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="audio file exceeds the 100 MB limit")
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise HTTPException(status_code=415, detail="audio does not contain a valid WAV header")
    return data, original_name


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_recording(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    device_id: str = Form(...),
    recorded_at: datetime = Form(...),
    duration_ms: int = Form(...),
    battery_pct: int | None = Form(None),
    db: Session = Depends(get_db),
) -> UploadResponse:
    _validate_metadata(device_id, recorded_at, duration_ms, battery_pct)
    data, original_name = await _read_wav(audio)
    file_sha256 = hashlib.sha256(
        device_id.strip().encode("utf-8") + recorded_at.isoformat().encode("utf-8") + data
    ).hexdigest()

    existing = db.scalar(select(Recording).where(Recording.file_sha256 == file_sha256))
    if existing is not None:
        return UploadResponse(id=existing.id, status="already_saved")

    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    recording_id = str(uuid4())
    stored_name = f"{recording_id}.wav"
    destination = settings.upload_dir / stored_name
    temporary = settings.upload_dir / f".{stored_name}.tmp"

    try:
        temporary.write_bytes(data)
        os.replace(temporary, destination)
        recording = Recording(
            id=recording_id,
            device_id=device_id.strip(),
            filename=original_name,
            file_path=str(destination),
            recorded_at=recorded_at,
            duration_ms=duration_ms,
            battery_pct=battery_pct,
            status="uploaded",
            file_sha256=file_sha256,
        )
        db.add(recording)
        db.commit()
    except IntegrityError:
        db.rollback()
        destination.unlink(missing_ok=True)
        duplicate = db.scalar(select(Recording).where(Recording.file_sha256 == file_sha256))
        if duplicate is None:
            raise HTTPException(status_code=500, detail="Could not save recording metadata")
        return UploadResponse(id=duplicate.id, status="already_saved")
    except OSError as exc:
        db.rollback()
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not save audio file") from exc
    except Exception:
        db.rollback()
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise

    recording.status = "processing"
    db.commit()
    background_tasks.add_task(process_recording, recording_id)
    return UploadResponse(id=recording_id, status="processing")
