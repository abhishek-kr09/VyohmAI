# Pocket Recorder

Pocket Recorder is a hardware-connected voice intelligence system that turns
short recordings into searchable, actionable knowledge.

Record on an ESP32-S3 device, upload over Wi-Fi, transcribe locally, extract
structured insights, ask grounded questions, and trigger safe agent-assisted
actions from one dashboard.

## What it does

- **Capture:** Button-controlled WAV recording on ESP32-S3 with microSD storage.
- **Sync:** Automatic Wi-Fi upload to a FastAPI backend with retry and duplicate protection.
- **Transcribe:** Timestamped speech-to-text using faster-whisper.
- **Understand:** Groq-powered summaries, topics, highlights, people, meetings, and action items.
- **Retrieve:** Session-scoped RAG for evidence-based questions over transcripts and actions.
- **Act:** Agent-driven local calendar events, email drafts, and action-item completion.
- **Review:** React dashboard for sessions, transcripts, audio playback, insights, and actions.

## Use cases

- Capture customer and vendor calls without taking notes.
- Search past conversations for decisions, commitments, and follow-ups.
- Ask, “What did I promise?” and receive answers grounded in transcript evidence.
- Convert meeting outcomes into a daily action queue.
- Prepare email drafts and calendar events without sending or scheduling anything automatically.
- Keep sensitive audio and transcripts in a local-first development environment.

## Architecture

```text
ESP32-S3 + microSD
        │ Wi-Fi multipart upload
        ▼
FastAPI + SQLite + local audio storage
        │
        ├── faster-whisper transcription
        ├── Groq structured insight extraction
        └── LangChain BM25 session-scoped RAG
        │
        ▼
React/Vite dashboard
```

### RAG approach

Pocket Recorder uses LangChain's `BM25Retriever` to retrieve relevant
timestamped transcript segments and pending action items. The selected session
can be used as a retrieval boundary, preventing answers from unrelated
recordings. The LLM receives only the retrieved evidence and returns citations;
when evidence is insufficient, the assistant says so instead of inventing an
answer.

## Capability levels

| Level | Capability |
| --- | --- |
| 0 | Development foundation, configuration, health checks |
| 1 | Validated WAV upload, metadata persistence, duplicate protection |
| 2 | Background transcription with timestamps and retry states |
| 3 | Session dashboard, search, playback, and transcript navigation |
| 4 | Structured AI insights and action-item extraction |
| 5 | Session-scoped RAG assistant with evidence citations |
| 6 | Agent-assisted local actions, calendar events, and email drafts |
| 7 | ESP32-S3 recording, storage, Wi-Fi upload, and retry workflow |
| 8 | Reliability tests and production-readiness checks |

## Tech stack

- **Backend:** Python, FastAPI, Uvicorn, SQLAlchemy, SQLite
- **Speech:** faster-whisper, PyAV
- **AI:** Groq-compatible API, LangChain, BM25
- **Frontend:** React, Vite, React Router, Axios
- **Hardware:** ESP32-S3, microSD, Wi-Fi, push button, microphone module

## Project structure

```text
backend/                 FastAPI API, services, models, and tests
frontend/                React/Vite dashboard
hardware/esp32_s3/       ESP32-S3 firmware and wiring/setup notes
.env.example             Safe configuration template
```

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- A Groq API key for chat, insights, and agent actions
- ESP32-S3 hardware for live capture (optional for local WAV testing)

## Local setup

### Backend

```powershell
cd D:\VyohmAI\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env`:

```env
GROQ_API_KEY=your_groq_api_key
LLM_MODEL=llama-3.1-8b-instant
```

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: <http://localhost:8000/health>

### Frontend

```powershell
cd D:\VyohmAI\frontend
npm install
npm run dev
```

Dashboard: <http://localhost:5173>

## Hardware flow

1. Configure Wi-Fi credentials and the backend computer's LAN IP in
   `hardware/esp32_s3/pocket_recorder_esp32_s3.ino`.
2. Keep the ESP32-S3 and backend computer on the same network.
3. Start the backend with `--host 0.0.0.0`.
4. Press the device button once to start recording and again to stop.
5. The device saves the WAV file to microSD and uploads it to `POST /upload`.
6. The backend transcribes the recording and makes the session available in
   the dashboard.

Failed uploads remain on the device for a later retry. The firmware must use
the computer's LAN IP, never `localhost`.

## Key API endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Service health |
| `POST /upload` | Hardware WAV upload |
| `GET /recordings` | Recording and session list |
| `GET /recordings/{id}` | Session details |
| `GET /recordings/{id}/transcript` | Timestamped transcript |
| `POST /recordings/{id}/extract` | Generate insights |
| `POST /chat` | Evidence-grounded assistant |
| `POST /actions/agent` | Execute approved local agent actions |
| `GET /actions/daily` | Pending action queue |

## Testing

Backend reliability tests:

```powershell
cd D:\VyohmAI\backend
.\.venv\Scripts\python.exe -m pytest
```

Frontend production build:

```powershell
cd D:\VyohmAI\frontend
npm run build
```

For a local end-to-end test, upload a valid WAV through the API or place a
recording on the ESP32-S3 and wait for its status to become `completed`.
Then open **Sessions**, review the transcript, and use **AI Assistant** or
**Actions**.

## Safety and privacy

- Never commit `.env`, API keys, databases, recordings, or virtual environments.
- Email actions create drafts only; they do not send email automatically.
- Calendar actions are stored locally; they do not connect to an external calendar.
- RAG answers are restricted to retrieved transcript and action evidence.