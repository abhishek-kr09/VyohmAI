from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str


class RecordingCreate(BaseModel):
    device_id: str
    recorded_at: datetime
    duration_ms: int
    battery_pct: int | None = None


class UploadResponse(BaseModel):
    id: str
    status: str


class RecordingResponse(BaseModel):
    id: str
    device_id: str
    filename: str
    recorded_at: datetime
    duration_ms: int
    battery_pct: int | None
    status: str
    created_at: datetime
    transcript_count: int = 0

    model_config = {"from_attributes": True}


class RecordingDetailResponse(RecordingResponse):
    transcript: list["TranscriptSegmentResponse"] = []
    insight: "InsightResponse | None" = None
    action_items: list["ActionItemResponse"] = []


class PersonInsight(BaseModel):
    name: str
    role: str | None = None


class MeetingInsight(BaseModel):
    date: str | None = None
    time: str | None = None
    purpose: str | None = None
    participants: list[str] = Field(default_factory=list)


class ActionItemResponse(BaseModel):
    id: str
    person: str | None
    task: str
    due_date: datetime | None
    status: str

    model_config = {"from_attributes": True}


class InsightResponse(BaseModel):
    id: str
    recording_id: str
    topic: str | None
    summary: str | None
    highlights: list[str] = Field(default_factory=list)
    people: list[PersonInsight] = Field(default_factory=list)
    meetings: list[MeetingInsight] = Field(default_factory=list)
    created_at: datetime


class InsightSessionResponse(BaseModel):
    recording_id: str
    session_name: str
    recorded_at: datetime
    duration_ms: int
    status: str
    insight: InsightResponse | None = None
    action_items: list[ActionItemResponse] = Field(default_factory=list)


class ExtractionResponse(BaseModel):
    recording_id: str
    status: str
    insight: InsightResponse | None = None
    action_items: list[ActionItemResponse] = Field(default_factory=list)


class SearchResultResponse(BaseModel):
    recording_id: str
    recording_name: str
    recorded_at: datetime
    start_time: float
    end_time: float
    text: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    recording_id: str | None = None


class ChatEvidence(BaseModel):
    recording_id: str
    recording_name: str
    start_time: float
    end_time: float
    quote: str


class ChatResponse(BaseModel):
    question: str
    answer: str
    evidence: list[ChatEvidence] = Field(default_factory=list)
    grounded: bool = True


class CalendarEventInput(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    start_time: datetime
    end_time: datetime
    attendees: list[str] = Field(default_factory=list)
    source_recording_id: str | None = None


class CalendarEventResponse(CalendarEventInput):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EmailDraftInput(BaseModel):
    recipient: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=10000)
    source_recording_id: str | None = None


class EmailDraftResponse(EmailDraftInput):
    id: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentInstructionRequest(BaseModel):
    instruction: str = Field(min_length=2, max_length=1000)
    recording_id: str | None = None


class AgentActionResponse(BaseModel):
    message: str
    action_type: str
    action_item_id: str | None = None
    calendar_event: CalendarEventResponse | None = None
    email_draft: EmailDraftResponse | None = None


class DailyActionResponse(ActionItemResponse):
    recording_name: str
    recorded_at: datetime


class TranscriptSegmentResponse(BaseModel):
    id: str
    start_time: float
    end_time: float
    text: str

    model_config = {"from_attributes": True}


class TranscriptionResponse(BaseModel):
    recording_id: str
    status: str
    segments: list[TranscriptSegmentResponse]
