from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Recording, TranscriptSegment
from app.schemas import SearchResultResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[SearchResultResponse])
def search_transcripts(
    q: str = Query(min_length=2, max_length=200),
    db: Session = Depends(get_db),
) -> list[SearchResultResponse]:
    query = q.strip()
    if not query:
        return []
    rows = db.execute(
        select(TranscriptSegment, Recording)
        .join(Recording, Recording.id == TranscriptSegment.recording_id)
        .where(TranscriptSegment.text.ilike(f"%{query}%"))
        .order_by(Recording.recorded_at.desc(), TranscriptSegment.start_time)
        .limit(100)
    ).all()
    return [
        SearchResultResponse(
            recording_id=recording.id,
            recording_name=recording.filename,
            recorded_at=recording.recorded_at,
            start_time=segment.start_time,
            end_time=segment.end_time,
            text=segment.text,
        )
        for segment, recording in rows
    ]
