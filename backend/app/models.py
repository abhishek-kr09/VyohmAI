from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_id() -> str:
    return str(uuid4())


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    device_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    battery_pct: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")
    file_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    transcript_segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="recording", cascade="all, delete-orphan"
    )
    insight: Mapped[Optional["RecordingInsight"]] = relationship(
        back_populates="recording", cascade="all, delete-orphan", uselist=False
    )
    action_items: Mapped[list["ActionItem"]] = relationship(
        back_populates="recording", cascade="all, delete-orphan"
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recording_id: Mapped[str] = mapped_column(ForeignKey("recordings.id"), nullable=False, index=True)
    start_time: Mapped[float] = mapped_column(nullable=False)
    end_time: Mapped[float] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    recording: Mapped[Recording] = relationship(back_populates="transcript_segments")


class RecordingInsight(Base):
    __tablename__ = "recording_insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recording_id: Mapped[str] = mapped_column(ForeignKey("recordings.id"), nullable=False, unique=True)
    topic: Mapped[Optional[str]] = mapped_column(String(255))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    highlights: Mapped[Optional[str]] = mapped_column(Text)
    people: Mapped[Optional[str]] = mapped_column(Text)
    meetings: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    recording: Mapped[Recording] = relationship(back_populates="insight")


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recording_id: Mapped[str] = mapped_column(ForeignKey("recordings.id"), nullable=False, index=True)
    person: Mapped[Optional[str]] = mapped_column(String(200))
    task: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    recording: Mapped[Recording] = relationship(back_populates="action_items")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attendees: Mapped[Optional[str]] = mapped_column(Text)
    source_recording_id: Mapped[Optional[str]] = mapped_column(ForeignKey("recordings.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class EmailDraft(Base):
    __tablename__ = "email_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source_recording_id: Mapped[Optional[str]] = mapped_column(ForeignKey("recordings.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
