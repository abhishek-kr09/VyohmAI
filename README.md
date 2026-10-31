# Pocket Recorder

Phases 0 through 3 establish the development foundation, audio pipeline, transcription workflow, and customer dashboard for the Pocket Recorder Intelligence System.

## Completed phases

### Phase 0 - Development foundation

**Use case:** A developer can start the backend and frontend independently and confirm that the application is healthy before uploading any recordings.

Delivered:

- FastAPI and Uvicorn backend
- React, Vite, Tailwind CSS, React Router, and Axios frontend
- SQLite database with SQLAlchemy ORM
- Initial recording, transcript, insight, action-item, calendar, and email-draft tables
- Environment-variable configuration
- `/health` endpoint
- FFmpeg installation and verification

### Phase 1 - Audio upload pipeline

**Use case:** A founder records a vendor call on an ESP32-S3 device. The device uploads the WAV file and metadata through `POST /upload`. The backend validates the request, saves the audio on disk, stores metadata in SQLite, and returns a recording ID. Retried uploads do not create duplicates or overwrite audio.

Delivered:

- Shared mock-recording and ESP32-S3 multipart upload contract
- WAV file and metadata validation
- Timezone-aware recording timestamps
- Safe UUID-based audio file storage
- SQLite recording persistence
- SHA-256 duplicate-upload protection
- `GET /recordings`
- Manifest upload script

### Phase 2 - Timestamped transcription

**Use case:** After a vendor call is uploaded, the backend converts the audio into searchable speech using faster-whisper. The founder can retrieve the transcript with exact start and end timestamps for each spoken segment.

Delivered:

- Background faster-whisper transcription
- `processing`, `completed`, and `failed` statuses
- Timestamped transcript segment persistence
- `GET /recordings/{recording_id}/transcript`
- Failed-transcription retry endpoint
- Compatible PyAV dependency pin
- Configurable Whisper model, device, and compute type

### Phase 3 - Customer dashboard

**Use case:** After a busy day, the founder opens Pocket Recorder and sees recent recordings, duration totals, and transcription readiness. They search for a phrase such as “vendor payment”, open the matching recording, play the original audio, and click a transcript timestamp to jump directly to that moment.

Delivered:

- Responsive SaaS-style dashboard
- Recordings library with status and device metadata
- Transcript search across recordings
- Recording details page
- Audio playback
- Clickable transcript timestamps with audio seeking
- Loading, empty, error, and failed-processing states
- Customer-friendly navigation

Phase 4 will add AI summaries, action items, people, and meeting extraction.

## Project structure

- `backend/` - FastAPI application, SQLAlchemy models, and local audio storage
- `frontend/` - React/Vite dashboard shell
- `sample-recordings/` - Mock recordings added in later phases

## Prerequisites

- Python 3.11+
- Node.js 20+
- FFmpeg on `PATH` (required for later audio processing)

## Backend setup - Command Prompt

```bat
cd backend
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --reload
```

## Backend setup - PowerShell

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload
```

The backend runs at `http://localhost:8000`. Health check: `GET /health`.

## Frontend setup - Command Prompt

```bat
cd frontend
npm install
npm run dev
```

The same commands work in PowerShell.

The frontend runs at `http://localhost:5173`.

## Phase 0 verification

1. Open `http://localhost:8000/health` and confirm `{"status":"ok"}`.
2. Open `http://localhost:5173` and confirm the Pocket Recorder shell loads.
3. Confirm `backend/pocket_recorder.db` exists after the backend starts.

Dashboard, search, AI, calendar, email, and the live hardware module are documented in their respective phase sections below.

## Phase 1 use case

A founder records a vendor call on an ESP32-S3 device. The device sends the WAV clip and metadata to `POST /upload`. The backend validates the request, saves the audio outside SQLite, stores the metadata in SQLite, and returns a recording ID. If the device retries the same clip, the backend returns the original ID without creating a duplicate or overwriting the audio file.

## Phase 1 testing

### 1. Start the backend

In PowerShell terminal 1:

```powershell
cd D:\VyohmAI\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

In PowerShell terminal 2, verify the health endpoint:

```powershell
curl.exe http://localhost:8000/health
```

Expected:

```json
{"status":"ok","service":"pocket-recorder-api","database":"configured"}
```

### 2. Create a test WAV file

If you do not already have a WAV file, run this from `D:\VyohmAI\backend`:

```powershell
@'
import wave

with wave.open("test-recording.wav", "wb") as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(16000)
    wav.writeframes(b"\x00\x00" * 16000)
'@ | .\.venv\Scripts\python.exe -
```

This creates a one-second, mono, 16-bit, 16 kHz WAV file.

### 3. Test a valid upload

```powershell
$response = curl.exe -sS -X POST http://localhost:8000/upload `
  -F "audio=@D:\VyohmAI\backend\test-recording.wav;type=audio/wav" `
  -F "device_id=esp32-001" `
  -F "recorded_at=2026-11-05T14:32:10+05:30" `
  -F "duration_ms=1000" `
  -F "battery_pct=85"

$response
```

Expected HTTP status: `201`.

Expected response shape:

```json
{"id":"<recording-id>","status":"processing"}
```

Confirm that a UUID-named WAV file exists in `backend/storage/recordings`.

### 4. Test duplicate retry handling

Run the same upload command again without changing the device, timestamp, or file.

Expected HTTP status: `201`, with:

```json
{"id":"<same-recording-id>","status":"already_saved"}
```

The second request must not create another database row or another audio file.

### 5. Test the recordings API

```powershell
curl.exe http://localhost:8000/recordings
```

The response should contain one recording with the submitted device ID, timestamp, duration, battery percentage, and a processing status such as `processing`, `completed`, or `failed`.

### 6. Test rejected uploads

Wrong file type:

```powershell
curl.exe -i -X POST http://localhost:8000/upload `
  -F "audio=@D:\VyohmAI\backend\test-recording.txt;type=text/plain" `
  -F "device_id=esp32-001" `
  -F "recorded_at=2026-11-05T14:32:10+05:30" `
  -F "duration_ms=1000"
```

Expected HTTP status: `415`.

Invalid battery percentage:

```powershell
curl.exe -i -X POST http://localhost:8000/upload `
  -F "audio=@D:\VyohmAI\backend\test-recording.wav;type=audio/wav" `
  -F "device_id=esp32-001" `
  -F "recorded_at=2026-11-05T14:32:10+05:30" `
  -F "duration_ms=1000" `
  -F "battery_pct=150"
```

Expected HTTP status: `422`.

Timezone-less timestamp:

```powershell
curl.exe -i -X POST http://localhost:8000/upload `
  -F "audio=@D:\VyohmAI\backend\test-recording.wav;type=audio/wav" `
  -F "device_id=esp32-001" `
  -F "recorded_at=2026-11-05T14:32:10" `
  -F "duration_ms=1000"
```

Expected HTTP status: `422`.

### 7. Test manifest uploads

Add a WAV file to `sample-recordings`, then edit `sample-recordings/manifest.json`:

```json
[
  {
    "filename": "vendor-call.wav",
    "device_id": "mock-device-001",
    "recorded_at": "2026-11-05T14:32:10+05:30",
    "duration_ms": 30000,
    "battery_pct": 85
  }
]
```

Run:

```powershell
cd D:\VyohmAI\backend
.\.venv\Scripts\python.exe scripts\upload_manifest.py
```

The script must print the same upload response returned by `POST /upload`. Verify the new recording with `curl.exe http://localhost:8000/recordings`.

### 8. Clean up the generated test file

```powershell
Remove-Item D:\VyohmAI\backend\test-recording.wav
```

## Phase 1 upload API

Start the backend, then upload a WAV file using the shared mock/hardware contract:

```powershell
curl.exe -X POST http://localhost:8000/upload `
  -F "audio=@D:\path\recording.wav;type=audio/wav" `
  -F "device_id=esp32-001" `
  -F "recorded_at=2026-11-05T14:32:10+05:30" `
  -F "duration_ms=30000" `
  -F "battery_pct=85"
```

Successful first upload returns HTTP 201:

```json
{"id":"<recording-id>","status":"processing"}
```

Retrying the exact same device, timestamp, and audio is idempotent and returns the existing ID with `already_saved`.

The manifest uploader uses the same endpoint:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\upload_manifest.py
```

Each manifest entry must contain `filename`, `device_id`, `recorded_at` with timezone, and `duration_ms`; `battery_pct` is optional.

## Phase 2 use case

After a founder uploads a vendor call, the backend transcribes the saved WAV file with faster-whisper. The transcript is stored as ordered segments with start and end timestamps, so later features can show the exact spoken context and seek audio to the relevant moment.

## Phase 2 transcription API

New endpoints:

- `GET /recordings/{recording_id}/transcript` - returns processing status and timestamped segments
- `POST /recordings/{recording_id}/transcribe` - retries a failed transcription

The upload response initially reports `processing`. The background job changes the recording to:

- `completed` when segments are saved
- `failed` when transcription cannot complete

Configure the local model in `backend/.env` if needed:

```env
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

The first transcription downloads the selected faster-whisper model. `small` provides better accuracy but needs more time and memory; use `tiny` for a faster development test.

The backend pins PyAV to a version compatible with `faster-whisper==1.1.1`. If dependencies were installed before Phase 2, reinstall them with:

```powershell
cd D:\VyohmAI\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

After changing Python dependencies, stop and restart Uvicorn.

## Phase 2 testing

1. Start the backend:

```powershell
cd D:\VyohmAI\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

2. Upload a real speech WAV file using the Phase 1 command. The response should be HTTP `201` with `status` set to `processing`.

3. Check the recording status:

```powershell
curl.exe http://localhost:8000/recordings
```

Wait until that recording's status is `completed`.

4. Retrieve the transcript:

```powershell
curl.exe http://localhost:8000/recordings/<recording-id>/transcript
```

Expected response:

```json
{
  "recording_id": "<recording-id>",
  "status": "completed",
  "segments": [
    {
      "id": "<segment-id>",
      "start_time": 0.0,
      "end_time": 4.5,
      "text": "Transcribed speech."
    }
  ]
}
```

5. Confirm that:

- Segments are ordered by `start_time`.
- Each segment has `start_time`, `end_time`, and non-empty text.
- The original WAV remains in `backend/storage/recordings`.
- The recording status is `completed`.

If transcription fails, the status becomes `failed`. Retry it with:

```powershell
curl.exe -X POST http://localhost:8000/recordings/<recording-id>/transcribe
```

Phase 2 does not yet include summaries, action-item extraction, search, or the dashboard transcript viewer.

## Phase 3 use case

A founder opens Pocket Recorder after a busy day and immediately sees their latest conversations, total recording time, and transcription readiness. They can search for a phrase such as "vendor payment", open the matching recording, play the original audio, and click any transcript timestamp to jump directly to that moment. This keeps the interface useful for customers even before AI summaries and action extraction are enabled.

## Phase 3 dashboard

Phase 3 adds:

- Responsive customer-facing dashboard with overview metrics
- Recordings library with processing status and device metadata
- Transcript search across recordings
- Recording detail page with audio playback
- Clickable timestamped transcript segments that seek the audio player
- Empty, loading, error, and failed-processing states
- AI Assistant navigation placeholder for the next intelligence phase

New backend endpoints:

- `GET /recordings/{recording_id}` - recording metadata and transcript
- `GET /recordings/{recording_id}/audio` - streams the stored WAV file
- `GET /search?q=...` - searches transcript text and returns recording/timestamp evidence

## Phase 3 testing

Start both services:

```powershell
cd D:\VyohmAI\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd D:\VyohmAI\frontend
npm run dev
```

Open `http://localhost:5173`.

Verify:

1. **Overview:** recording counts, duration, and transcription counts are visible.
2. **Recordings:** the library lists uploaded recordings and statuses.
3. **Search:** enter at least two characters, such as `students` or `vendor`; matching transcript segments appear.
4. **Details:** click a recording to see metadata and transcript segments.
5. **Playback:** click the audio controls and confirm the WAV plays.
6. **Timestamp seek:** click a transcript row and confirm playback jumps to its timestamp.
7. **Responsive layout:** narrow the browser window and confirm the sidebar collapses to icons and content remains usable.

The same checks are available through the API:

```powershell
curl.exe http://localhost:8000/recordings
curl.exe http://localhost:8000/search?q=students
curl.exe http://localhost:8000/recordings/<recording-id>
curl.exe http://localhost:8000/recordings/<recording-id>/audio --output recording-copy.wav
```

Phase 3 does not yet include AI summaries, action-item extraction, grounded chat responses, calendar events, or email drafts. These are covered by later phases.

## Phase 4 use case

After reviewing a transcribed vendor call, the founder chooses **Generate insights**. Pocket Recorder sends only the timestamped transcript to the configured Groq LLM and requests strict JSON. The backend validates the response, stores a concise summary, mentioned people, meeting details, and action items, then displays them on the recording page. Missing information remains `null` or an empty list; the model is instructed not to invent facts.

## Phase 4 structured insights

Delivered:

- Groq-compatible structured JSON extraction
- Pydantic validation of LLM output
- Summary persistence in `recording_insights`
- People and meeting persistence as validated JSON
- Action-item persistence in `action_items`
- Recording details API includes `insight` and `action_items`
- `POST /recordings/{recording_id}/extract`
- Customer-facing insights panel on recording details
- Explicit configuration errors when LLM credentials are missing

Configure `backend/.env` before using extraction:

```env
GROQ_API_KEY=your_groq_api_key
LLM_MODEL=your_available_groq_model
```

Never commit or share the `.env` file.

## Phase 4 testing

1. Start the backend and frontend using the Phase 3 commands.
2. Confirm the recording has a completed transcript:

```powershell
curl.exe http://localhost:8000/recordings/<recording-id>/transcript
```

3. Configure `GROQ_API_KEY` and `LLM_MODEL`, then restart Uvicorn.
4. Open the recording details page in the dashboard and click **Generate insights**.
5. Or call the API directly:

```powershell
curl.exe -X POST http://localhost:8000/recordings/<recording-id>/extract
```

Expected initial response:

```json
{
  "recording_id": "<recording-id>",
  "status": "processing",
  "insight": null,
  "action_items": []
}
```

6. After processing, retrieve the recording:

```powershell
curl.exe http://localhost:8000/recordings/<recording-id>
```

The response contains:

- `insight.summary`
- `insight.people`
- `insight.meetings`
- `action_items`

If the key or model is missing, extraction fails explicitly and no fabricated insight is saved.

Speaker diarization and generic `Person 1`/`Person 2` labels are intentionally out of scope. Phase 4 extracts people mentioned in the transcript, which is the behavior required by the challenge brief. faster-whisper remains responsible only for speech-to-text.

## Level 4 / Phase 5 - Ask

### Use case

After recordings have been transcribed, a founder asks the AI Assistant a natural-language question such as **“What did I promise?”**, **“Show my pending tasks”**, or **“Find vendor discussions.”** The backend first retrieves matching transcript evidence and only then asks the configured LLM to answer. The response includes the recording filename, timestamp, and quoted transcript evidence used for each factual answer.

### Grounding contract

- `POST /chat` accepts a question between 2 and 500 characters.
- Retrieval is performed by server-side tools; the model cannot execute SQL or Python.
- Questions with no matching evidence return an explicit unavailable answer.
- Model citations are checked against the retrieved evidence indexes before they are returned.
- Invalid or missing Groq configuration returns an explicit API error.
- Speaker identity is not inferred from names mentioned in text.

Example request:

```powershell
curl.exe -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d '{\"question\":\"What did I promise?\"}'
```

Example response shape:

```json
{
  "question": "What did I promise?",
  "answer": "You said you would send the quotation on Friday.",
  "grounded": true,
  "evidence": [
    {
      "recording_id": "<recording-id>",
      "recording_name": "vendor-call.wav",
      "start_time": 42.1,
      "end_time": 47.8,
      "quote": "I will send the quotation on Friday."
    }
  ]
}
```

### Level 4 testing

1. Start the backend with a valid `GROQ_API_KEY` and `LLM_MODEL`.
2. Open **AI Assistant** in the dashboard.
3. Ask a question supported by a transcript and confirm the answer shows an evidence card with a recording and timestamp.
4. Ask about information absent from all recordings and confirm the assistant says it does not have enough evidence.
5. Test the API directly:

```powershell
curl.exe -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d '{\"question\":\"Show my pending tasks\"}'
```

Level 4 does not create calendar events or send emails. Those actions require a later confirmation-based phase.

## Level 5 / Phase 6 - Act

Level 5 turns extracted information into safe, user-approved actions.

Delivered:

- **Actions** dashboard
- Calendar event preview and confirmation
- Local calendar event persistence in `calendar_events`
- Email draft preview and confirmation
- Local email draft persistence in `email_drafts`
- Optional source-recording links
- Attendee and recipient validation
- Explicit confirmation required before persistence
- No external calendar API integration
- No email is ever sent automatically

Open **Actions** in the dashboard to create an event or email draft. The workflow is:

```text
Enter details -> Preview -> Confirm -> Save locally
```

API endpoints:

```text
GET  /actions/calendar-events
POST /actions/calendar-events/preview
POST /actions/calendar-events?confirmed=true
GET  /actions/email-drafts
POST /actions/email-drafts/preview
POST /actions/email-drafts?confirmed=true
```

If `confirmed=true` is omitted, the create endpoints return `409` and do not write anything. These actions are intentionally local placeholders until a real calendar provider and email delivery service are configured.

### Level 5 testing

1. Start the backend and frontend.
2. Open `http://localhost:5173/actions`.
3. Enter a calendar title, start time, and end time. Click **Preview event**, verify the preview, then click **Confirm**.
4. Confirm the event appears under **Calendar events**.
5. Enter a recipient, subject, and body. Click **Preview draft**, verify the preview, then click **Confirm**.
6. Confirm the draft appears under **Email drafts**.
7. Cancel a preview and confirm that no item is saved.
8. Test the confirmation guard:

```powershell
curl.exe -i -X POST "http://localhost:8000/actions/calendar-events" `
  -H "Content-Type: application/json" `
  -d '{\"title\":\"Unconfirmed event\",\"start_time\":\"2026-11-05T10:00:00+05:30\",\"end_time\":\"2026-11-05T11:00:00+05:30\"}'
```

Expected status: `409`.

## Phase 7 - ESP32-S3 Hardware Integration

The hardware upload path is now provided in `hardware/esp32_s3`. The firmware
template records mono 16-bit WAV audio from an I2S microphone, saves it to
microSD, uploads it as multipart form data, and removes the local file only
after a successful 2xx response. Failed uploads remain on the card so the
device can retry them.

The backend upload contract is:

```text
POST /upload
audio=<WAV file>
device_id=<device identifier>
recorded_at=<ISO-8601 timestamp with timezone>
duration_ms=<recording duration>
battery_pct=<optional 0-100 value>
```

### Live hardware setup

1. Connect the ESP32-S3 and I2S microphone/microSD hardware according to the
   board-specific wiring.
2. Edit Wi-Fi credentials, server LAN IP, device ID, and pin constants in
   `hardware/esp32_s3/pocket_recorder_esp32_s3.ino`.
3. Start FastAPI on the LAN:

```powershell
cd D:\VyohmAI\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

4. Flash the sketch from Arduino IDE or PlatformIO.
5. Press the device button once to start recording and again to stop.
6. Confirm the device receives a 2xx response and the recording appears in:

```powershell
curl.exe http://localhost:8000/recordings
```

7. Open the dashboard and wait for transcription to complete.

The computer and ESP32 must be on the same network. Replace the server IP in
the sketch with the computer's LAN IPv4 address; `localhost` points back to
the ESP32 and will not work. Windows Firewall must allow inbound TCP port
`8000`.

### Hardware validation

- Verify a WAV file is created on the SD card.
- Verify the upload reaches `POST /upload`.
- Verify the recording appears in the dashboard.
- Power off or disconnect Wi-Fi during upload and verify the file remains on
  the card.
- Retry the same file and verify the backend returns the same recording ID
  with `already_saved`.
- Verify invalid metadata is rejected by the backend.

The firmware is configurable rather than board-certified: exact I2S, SD, and
battery pins vary by ESP32-S3 board. Physical recording quality and wiring
must be tested on the selected hardware before calling the integration
production-ready.

## Phase 8 / Level 6 - Testing and Reliability

Level 6 adds honest failure handling and live behavior across the application.

Delivered:

- Focused backend reliability tests for metadata validation, WAV validation,
  and unknown-question behavior
- Automatic recording refresh every five seconds on the dashboard and library
- Automatic transcript refresh while transcription is processing
- In-app retry control for failed transcription
- Explicit loading, error, processing, and unavailable-evidence states
- Live upload verification without restarting FastAPI

Run the focused backend tests:

```powershell
cd D:\VyohmAI\backend
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
```

### Level 6 manual verification

1. Upload a valid WAV and confirm `201` with `processing`.
2. Upload the same device, timestamp, and bytes again. Confirm
   `already_saved` and the same recording ID.
3. Submit a non-WAV file, malformed WAV, missing metadata, timezone-less
   timestamp, zero duration, and battery outside `0-100`; confirm rejection.
4. Open **Recordings**, upload another file while the page is open, and confirm
   it appears within five seconds without restarting the backend.
5. Open a processing recording and confirm its transcript updates
   automatically.
6. Force or observe a transcription failure, click **Retry transcription**, and
   confirm it returns to `processing`.
7. Ask the Assistant about information absent from all recordings and confirm
   `grounded: false` with no evidence.
8. Upload from the ESP32 on the same LAN and confirm the new recording appears
   without a server restart.

Physical ESP32 validation remains dependent on the selected board, microphone,
SD wiring, Wi-Fi, and firewall configuration described in Phase 7.

## Session insights

Each hardware button cycle is one session: press once to start recording and
press again to stop and upload the WAV. The new **Insights** sidebar page
groups sessions by recording date. Select a session to view its topic,
summary, important highlights, people, and action items, then open the full
transcript and audio from the session link.

Insight extraction now requests:

```text
topic, summary, highlights, people, meetings, action_items
```

Existing SQLite databases are upgraded automatically with the new topic and
highlights columns. Sessions recorded before this change remain available;
their new fields are shown as unavailable until insights are regenerated.

## Session-scoped RAG

The Assistant uses LangChain's `BM25Retriever` to rank transcript and pending
action-item `Document` objects before the Groq answer step. This provides RAG
without requiring a separate vector database or embedding API. Retrieval is
restricted to one session when a recording ID is supplied. From an expanded
session in **Insights**, choose **Ask about this session**. The request sends
the selected `recording_id`; transcript search and action-item retrieval then
filter to that recording before the LLM receives evidence.

```text
POST /chat
{
  "question": "What was decided?",
  "recording_id": "<session-recording-id>"
}
```

Without a `recording_id`, the Assistant searches across recordings. With one,
cross-session evidence cannot be returned. An unknown recording ID is rejected
with `404`.

The current retriever is lexical BM25. If semantic similarity is needed later,
the document-building boundary can be reused with a persistent LangChain vector
store and an approved embeddings provider; session metadata filtering must remain
mandatory.

### VS Code Python interpreter

The repository includes `.vscode/settings.json` pointing Python and Pylance to
`backend/.venv`. If imports such as `langchain_core`, `langchain_community`, or
`sqlalchemy` are still underlined, run **Python: Select Interpreter** and choose
`backend/.venv/Scripts/python.exe`, then reload the VS Code window.

### Groq 401 troubleshooting

`401 Unauthorized` means the Groq API key is invalid, revoked, expired, or belongs to a different provider. Keys shown in screenshots or shared in chat must be revoked and replaced.

1. Open `https://console.groq.com/keys`.
2. Revoke the exposed key and create a new Groq key.
3. Update only the value in `backend/.env`:

```env
GROQ_API_KEY=your_new_groq_key
LLM_MODEL=openai/gpt-oss-20b
```

4. Restart Uvicorn so the environment file is reloaded.
5. Retry the extraction request.

Never use an xAI/Grok key with the Groq endpoint, and never paste the key into a terminal screenshot or chat message.
