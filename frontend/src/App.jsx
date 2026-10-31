import { useEffect, useMemo, useRef, useState } from "react";
import { BrowserRouter, Link, NavLink, Route, Routes, useNavigate, useParams, useSearchParams } from "react-router-dom";
import api from "./services/api";
import "./index.css";

const navItems = [
  { to: "/", label: "Overview", icon: "⌂", end: true },
  { to: "/recordings", label: "Recordings", icon: "◉" },
  { to: "/assistant", label: "AI Assistant", icon: "✦" },
  { to: "/actions", label: "Actions", icon: "✓" },
  { to: "/insights", label: "Insights", icon: "▣" },
];

function Layout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <span className="brand-mark">P</span>
          <span>Pocket<span>Recorder</span></span>
        </Link>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              <span>{item.icon}</span>{item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="status-dot"><span /> System operational</div>
          <div className="user-card"><div className="avatar">AK</div><div><strong>My workspace</strong><small>Personal account</small></div></div>
        </div>
      </aside>
      <main className="main-content">
        <header className="topbar"><div className="mobile-brand">PocketRecorder</div><div className="topbar-actions"><span className="topbar-date">{new Date().toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}</span><button className="icon-button" aria-label="Notifications">⌁</button><div className="avatar small">AK</div></div></header>
        <div className="page-container"><Routes><Route path="/" element={<Dashboard />} /><Route path="/recordings" element={<Recordings />} /><Route path="/recordings/:recordingId" element={<RecordingDetails />} /><Route path="/assistant" element={<Assistant />} /><Route path="/actions" element={<Actions />} /><Route path="/insights" element={<Insights />} /></Routes></div>
      </main>
    </div>
  );
}

function Dashboard() {
  const [recordings, setRecordings] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = () => api.get("/recordings").then((response) => { if (active) { setRecordings(response.data); setError(""); } }).catch(() => { if (active) setError("Could not load recordings. Is the backend running?"); });
    load();
    const timer = setInterval(load, 5000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  const totalSeconds = recordings.reduce((sum, item) => sum + item.duration_ms / 1000, 0);
  const completed = recordings.filter((item) => item.status === "completed").length;
  return <><PageHeading eyebrow="YOUR WORKSPACE" title="Good morning, Abhishek" subtitle="Here's what's happening with your recordings." action={<Link className="primary-button" to="/recordings">View recordings <span>→</span></Link>} />
    {error && <ErrorBanner message={error} />}
    <div className="stat-grid"><Stat label="Total recordings" value={recordings.length} detail="All time" icon="◉" /><Stat label="Total duration" value={formatDuration(totalSeconds)} detail="Across all recordings" icon="◷" /><Stat label="Transcribed" value={`${completed}/${recordings.length}`} detail="Ready to review" icon="✓" /></div>
    <section className="content-card recent-card"><div className="section-heading"><div><h2>Recent recordings</h2><p>Your latest conversations, all in one place.</p></div><Link to="/recordings" className="text-link">View all <span>→</span></Link></div>{recordings.length === 0 ? <EmptyState title="No recordings yet" text="Upload your first recording to start building your knowledge base." /> : <RecordingTable recordings={recordings.slice(0, 5)} />}</section>
  </>;
}

function Recordings() {
  const [recordings, setRecordings] = useState([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = () => api.get("/recordings").then((response) => { if (active) { setRecordings(response.data); setError(""); setLoading(false); } }).catch(() => { if (active) { setError("Could not load recordings. Is the backend running?"); setLoading(false); } });
    load();
    const timer = setInterval(load, 5000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  useEffect(() => { const timer = setTimeout(() => { if (query.trim().length >= 2) api.get("/search", { params: { q: query } }).then((response) => setResults(response.data)); else setResults(null); }, 250); return () => clearTimeout(timer); }, [query]);
  return <><PageHeading eyebrow="LIBRARY" title="Recordings" subtitle="Review, search, and revisit every conversation." />{error && <ErrorBanner message={error} />}<div className="search-wrap"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search conversations, names, or topics..." /><kbd>⌘ K</kbd></div>{results ? <SearchResults results={results} /> : loading ? <Loading /> : <section className="content-card"><div className="section-heading"><div><h2>All recordings</h2><p>{recordings.length} conversation{recordings.length === 1 ? "" : "s"} · updates automatically</p></div></div><RecordingTable recordings={recordings} /></section>}</>;
}

function RecordingDetails() {
  const { recordingId } = useParams();
  const [recording, setRecording] = useState(null);
  const [error, setError] = useState("");
  const audioRef = useRef(null);
  useEffect(() => {
    let active = true;
    const load = () => api.get(`/recordings/${recordingId}`).then((response) => { if (active) { setRecording(response.data); setError(""); } }).catch(() => { if (active) setError("This recording could not be found."); });
    load();
    const timer = setInterval(() => { if (active && recording?.status !== "completed" && recording?.status !== "failed") load(); }, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [recordingId, recording?.status]);
  if (error) return <ErrorBanner message={error} />;
  if (!recording) return <Loading />;
  const seek = (seconds) => { if (audioRef.current) { audioRef.current.currentTime = seconds; audioRef.current.play(); } };
  const retry = async () => {
    try {
      await api.post(`/recordings/${recording.id}/transcribe`);
      setRecording({ ...recording, status: "processing", transcript: [] });
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Could not retry transcription.");
    }
  };
  return <><Link className="back-link" to="/recordings">← Back to recordings</Link><PageHeading eyebrow="RECORDING" title={recording.filename} subtitle={`${formatDate(recording.recorded_at)} · ${recording.device_id}`} /><div className="detail-layout"><section className="content-card transcript-card"><div className="section-heading"><div><h2>Transcript</h2><p>{recording.transcript.length} timestamped segments{recording.status === "processing" ? " · updating automatically" : ""}</p></div><Status status={recording.status} /></div><audio ref={audioRef} controls className="audio-player" src={`${api.defaults.baseURL}/recordings/${recording.id}/audio`} />{recording.transcript.length ? <div className="transcript-list">{recording.transcript.map((segment) => <button className="transcript-row" key={segment.id} onClick={() => seek(segment.start_time)}><span className="timestamp">{formatTime(segment.start_time)}</span><span>{segment.text}</span></button>)}</div> : <EmptyState title="Transcript not available" text={recording.status === "failed" ? "Transcription failed. Retry it below." : "This recording is still being processed. This page checks for updates automatically."} />}{recording.status === "failed" && <button className="primary-button retry-button" onClick={retry}>Retry transcription <span>↻</span></button>}</section><aside className="content-card metadata-card"><h2>Recording details</h2><Meta label="Recorded" value={formatDate(recording.recorded_at)} /><Meta label="Duration" value={formatDuration(recording.duration_ms / 1000)} /><Meta label="Device" value={recording.device_id} /><Meta label="Battery" value={recording.battery_pct == null ? "USB powered" : `${recording.battery_pct}%`} /></aside></div><InsightPanel recording={recording} /></>;
}

function InsightPanel({ recording }) {
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState("");
  if (!recording.insight && recording.status === "completed") {
    const generate = async () => {
      setExtracting(true);
      setError("");
      try {
        await api.post(`/recordings/${recording.id}/extract`);
        window.location.reload();
      } catch {
        setError("Insights could not be generated. Check the LLM configuration and try again.");
        setExtracting(false);
      }
    };
    return <section className="content-card insight-panel"><div className="assistant-icon">✦</div><h2>Understand this recording</h2><p>Generate a grounded summary, people, meetings, and action items from the transcript.</p>{error && <div className="error-banner">{error}</div>}<button className="primary-button" onClick={generate} disabled={extracting}>{extracting ? "Generating..." : "Generate insights"} {!extracting && <span>→</span>}</button></section>;
  }
  if (!recording.insight) return null;
  return <section className="content-card insight-panel"><div className="section-heading"><div><h2>AI insights</h2><p>Structured information extracted from this transcript.</p></div><span className="status completed"><span />ready</span></div>{recording.insight.summary && <p className="insight-summary">{recording.insight.summary}</p>}<div className="insight-columns"><div><h3>People</h3>{recording.insight.people.length ? recording.insight.people.map((person) => <div className="insight-item" key={person.name}><strong>{person.name}</strong><span>{person.role || "Mentioned in transcript"}</span></div>) : <p className="muted">No people identified.</p>}</div><div><h3>Action items</h3>{recording.action_items.length ? recording.action_items.map((item) => <div className="insight-item" key={item.id}><strong>{item.task}</strong><span>{item.person || "Owner not specified"}{item.due_date ? ` · Due ${formatDate(item.due_date)}` : ""}</span></div>) : <p className="muted">No action items identified.</p>}</div></div></section>;
}

function Assistant() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("recording_id");
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const suggestions = ["What did I promise?", "Show my pending tasks", "Find vendor discussions"];
  const ask = async (event) => {
    event?.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError("");
    try {
      const result = await api.post("/chat", { question: question.trim(), recording_id: sessionId || null });
      setResponse(result.data);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "The assistant could not answer right now.");
      setResponse(null);
    } finally {
      setLoading(false);
    }
  };
  return <><PageHeading eyebrow="INTELLIGENCE" title="AI Assistant" subtitle={sessionId ? "Ask questions grounded only in this session." : "Ask questions about your recorded conversations."} />
    <section className="assistant-card content-card">
      <div className="assistant-icon">✦</div>
      <h2>Your recordings, made useful.</h2>
      <p>{sessionId ? "This session is the only source used for retrieval and evidence." : "Answers are grounded in transcript evidence. Each factual answer includes the recording and timestamp used."}</p>
      <form className="chat-form" onSubmit={ask}><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about your conversations..." maxLength={500} /><button className="primary-button" disabled={loading || !question.trim()}>{loading ? "Thinking..." : "Ask"} {!loading && <span>→</span>}</button></form>
      <div className="suggestion-row">{suggestions.map((suggestion) => <button key={suggestion} onClick={() => setQuestion(suggestion)}>{suggestion}</button>)}</div>
    </section>
    {error && <ErrorBanner message={error} />}
    {response && <section className="content-card chat-response"><div className="section-heading"><div><h2>Answer</h2><p>{response.grounded ? "Grounded in your recordings" : "No verified evidence"}</p></div></div><p className="answer-text">{response.answer}</p>{response.evidence.length ? <div className="evidence-list"><h3>Evidence</h3>{response.evidence.map((item) => <Link className="evidence-item" to={`/recordings/${item.recording_id}`} key={`${item.recording_id}-${item.start_time}`}><div><strong>{item.recording_name}</strong><span>{formatTime(item.start_time)} - {formatTime(item.end_time)}</span></div><p>{item.quote}</p></Link>)}</div> : <p className="muted">No transcript evidence was found for this answer.</p>}</section>}
  </>;
}

function Actions() {
  const [recordings, setRecordings] = useState([]);
  const [events, setEvents] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [calendar, setCalendar] = useState({ title: "", description: "", start_time: "", end_time: "", attendees: "", source_recording_id: "" });
  const [email, setEmail] = useState({ recipient: "", subject: "", body: "", source_recording_id: "" });
  const [calendarPreview, setCalendarPreview] = useState(null);
  const [emailPreview, setEmailPreview] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api.get("/recordings"), api.get("/actions/calendar-events"), api.get("/actions/email-drafts")])
      .then(([recordingResult, eventResult, draftResult]) => {
        setRecordings(recordingResult.data);
        setEvents(eventResult.data);
        setDrafts(draftResult.data);
      })
      .catch(() => setError("Could not load saved actions."));
  }, []);
  const previewEvent = async (event) => {
    event.preventDefault();
    setError("");
    try {
      const payload = { ...calendar, start_time: new Date(calendar.start_time).toISOString(), end_time: new Date(calendar.end_time).toISOString(), attendees: calendar.attendees.split(",").map((item) => item.trim()).filter(Boolean) };
      const result = await api.post("/actions/calendar-events/preview", payload);
      setCalendarPreview(result.data);
    } catch (requestError) { setError(requestError.response?.data?.detail || "Could not preview the calendar event."); }
  };
  const confirmEvent = async () => {
    try {
      const result = await api.post("/actions/calendar-events?confirmed=true", calendarPreview);
      setEvents((items) => [...items, result.data].sort((a, b) => new Date(a.start_time) - new Date(b.start_time)));
      setCalendarPreview(null);
      setCalendar({ title: "", description: "", start_time: "", end_time: "", attendees: "", source_recording_id: "" });
    } catch (requestError) { setError(requestError.response?.data?.detail || "Could not create the calendar event."); }
  };
  const previewEmail = async (event) => {
    event.preventDefault();
    setError("");
    try {
      const result = await api.post("/actions/email-drafts/preview", email);
      setEmailPreview(result.data);
    } catch (requestError) { setError(requestError.response?.data?.detail || "Could not preview the email draft."); }
  };
  const confirmEmail = async () => {
    try {
      const result = await api.post("/actions/email-drafts?confirmed=true", emailPreview);
      setDrafts((items) => [result.data, ...items]);
      setEmailPreview(null);
      setEmail({ recipient: "", subject: "", body: "", source_recording_id: "" });
    } catch (requestError) { setError(requestError.response?.data?.detail || "Could not save the email draft."); }
  };
  return <><PageHeading eyebrow="ACTIONS" title="Turn insights into action" subtitle="Preview first, then confirm. Pocket Recorder never sends email or creates external events automatically." />{error && <ErrorBanner message={error} />}
    <div className="actions-grid">
      <section className="content-card action-card"><div className="section-heading"><div><h2>Calendar event</h2><p>Create a local event after confirmation.</p></div><span className="action-badge">CONFIRM</span></div><form className="action-form" onSubmit={previewEvent}><input required placeholder="Event title" value={calendar.title} onChange={(event) => setCalendar({ ...calendar, title: event.target.value })} /><textarea placeholder="Description" value={calendar.description} onChange={(event) => setCalendar({ ...calendar, description: event.target.value })} /><div className="form-row"><label>Start<input required type="datetime-local" value={calendar.start_time} onChange={(event) => setCalendar({ ...calendar, start_time: event.target.value })} /></label><label>End<input required type="datetime-local" value={calendar.end_time} onChange={(event) => setCalendar({ ...calendar, end_time: event.target.value })} /></label></div><input placeholder="Attendees (comma-separated emails)" value={calendar.attendees} onChange={(event) => setCalendar({ ...calendar, attendees: event.target.value })} /><select value={calendar.source_recording_id} onChange={(event) => setCalendar({ ...calendar, source_recording_id: event.target.value })}><option value="">Source recording (optional)</option>{recordings.map((recording) => <option value={recording.id} key={recording.id}>{recording.filename}</option>)}</select><button className="primary-button">Preview event <span>→</span></button></form>{calendarPreview && <Confirmation title="Confirm calendar event" text={`${calendarPreview.title} · ${formatDate(calendarPreview.start_time)}`} onConfirm={confirmEvent} onCancel={() => setCalendarPreview(null)} />}</section>
      <section className="content-card action-card"><div className="section-heading"><div><h2>Email draft</h2><p>Save a draft for review. Nothing is sent.</p></div><span className="action-badge">DRAFT</span></div><form className="action-form" onSubmit={previewEmail}><input required type="email" placeholder="Recipient email" value={email.recipient} onChange={(event) => setEmail({ ...email, recipient: event.target.value })} /><input required placeholder="Subject" value={email.subject} onChange={(event) => setEmail({ ...email, subject: event.target.value })} /><textarea required rows="5" placeholder="Email body" value={email.body} onChange={(event) => setEmail({ ...email, body: event.target.value })} /><select value={email.source_recording_id} onChange={(event) => setEmail({ ...email, source_recording_id: event.target.value })}><option value="">Source recording (optional)</option>{recordings.map((recording) => <option value={recording.id} key={recording.id}>{recording.filename}</option>)}</select><button className="primary-button">Preview draft <span>→</span></button></form>{emailPreview && <Confirmation title="Save this email draft?" text={`${emailPreview.recipient} · ${emailPreview.subject}`} onConfirm={confirmEmail} onCancel={() => setEmailPreview(null)} />}</section>
    </div>
    <div className="saved-actions"><section className="content-card saved-card"><div className="section-heading"><div><h2>Calendar events</h2><p>{events.length} saved event{events.length === 1 ? "" : "s"}</p></div></div>{events.length ? events.map((event) => <div className="saved-item" key={event.id}><strong>{event.title}</strong><span>{formatDate(event.start_time)}{event.attendees.length ? ` · ${event.attendees.join(", ")}` : ""}</span></div>) : <p className="muted">No calendar events yet.</p>}</section><section className="content-card saved-card"><div className="section-heading"><div><h2>Email drafts</h2><p>{drafts.length} saved draft{drafts.length === 1 ? "" : "s"}</p></div></div>{drafts.length ? drafts.map((draft) => <div className="saved-item" key={draft.id}><strong>{draft.subject}</strong><span>{draft.recipient} · {draft.status}</span></div>) : <p className="muted">No email drafts yet.</p>}</section></div>
  </>;
}

function Insights() {
  const [sessions, setSessions] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = () => api.get("/recordings/insights").then((response) => { if (active) { setSessions(response.data); setError(""); } }).catch(() => { if (active) setError("Could not load session insights."); });
    load();
    const timer = setInterval(load, 5000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  const groups = sessions.reduce((result, session) => {
    const date = new Date(session.recorded_at).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric", year: "numeric" });
    (result[date] ||= []).push(session);
    return result;
  }, {});
  return <><PageHeading eyebrow="KNOWLEDGE" title="Session insights" subtitle="Review what happened in each recording, organized by date." />{error && <ErrorBanner message={error} />}{!sessions.length ? <section className="content-card"><EmptyState title="No sessions yet" text="Record a session on the device and its insights will appear here after transcription and extraction." /></section> : <div className="insights-groups">{Object.entries(groups).map(([date, items]) => <section className="insight-date-group" key={date}><h2>{date}</h2><div className="session-list">{items.map((session) => <article className={`session-card content-card ${selected?.recording_id === session.recording_id ? "selected" : ""}`} key={session.recording_id}><button className="session-header" onClick={() => setSelected(selected?.recording_id === session.recording_id ? null : session)}><div className="session-icon">✦</div><div><strong>{session.insight?.topic || session.session_name}</strong><span>{formatTime(Math.max(0, session.duration_ms / 1000))} · {session.status}</span></div><span className="session-chevron">{selected?.recording_id === session.recording_id ? "⌃" : "⌄"}</span></button>{selected?.recording_id === session.recording_id && <div className="session-insight">{session.insight ? <><div className="insight-block"><h3>Topic</h3><p>{session.insight.topic || "Topic not identified"}</p></div><div className="insight-block"><h3>Summary</h3><p>{session.insight.summary || "No summary available."}</p></div><div className="insight-block"><h3>Important highlights</h3>{session.insight.highlights.length ? <ul>{session.insight.highlights.map((highlight, index) => <li key={`${session.recording_id}-highlight-${index}`}>{highlight}</li>)}</ul> : <p>No highlights identified.</p>}</div>  <div className="insight-block"><h3>Action items</h3>{session.action_items.length ? <ul>{session.action_items.map((item) => <li key={item.id}>{item.task}{item.person ? ` · ${item.person}` : ""}</li>)}</ul> : <p>No action items identified.</p>}<div className="session-links"><Link className="text-link" to={`/assistant?recording_id=${session.recording_id}`}>Ask about this session <span>→</span></Link><Link className="text-link" to={`/recordings/${session.recording_id}`}>Open full session <span>→</span></Link></div></div></> : <p className="muted">Insights are not ready. Open the recording to generate them after transcription completes.</p>}</div>}</article>)}</div></section>)}</div>}</>;
}

function Confirmation({ title, text, onConfirm, onCancel }) {
  return <div className="confirmation"><div><strong>{title}</strong><span>{text}</span></div><div><button className="secondary-button" onClick={onCancel}>Cancel</button><button className="primary-button" onClick={onConfirm}>Confirm</button></div></div>;
}

function PageHeading({ eyebrow, title, subtitle, action }) { return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>; }
function Stat({ label, value, detail, icon }) { return <div className="stat-card"><div className="stat-icon">{icon}</div><div><p>{label}</p><strong>{value}</strong><small>{detail}</small></div></div>; }
function RecordingTable({ recordings }) { return <div className="recording-list">{recordings.map((recording) => <Link className="recording-item" to={`/recordings/${recording.id}`} key={recording.id}><div className="recording-icon">♫</div><div className="recording-info"><strong>{recording.filename}</strong><span>{formatDate(recording.recorded_at)} · {recording.device_id}</span></div><span className="recording-duration">{formatDuration(recording.duration_ms / 1000)}</span><Status status={recording.status} /><span className="chevron">›</span></Link>)}</div>; }
function SearchResults({ results }) { return <section className="content-card"><div className="section-heading"><div><h2>Search results</h2><p>{results.length} matching transcript segment{results.length === 1 ? "" : "s"}</p></div></div>{results.length ? <div className="search-results">{results.map((result, index) => <Link to={`/recordings/${result.recording_id}`} className="result-item" key={`${result.recording_id}-${index}`}><div><strong>{result.recording_name}</strong><span>{formatDate(result.recorded_at)} · {formatTime(result.start_time)}</span></div><p>{highlight(result.text)}</p></Link>)}</div> : <EmptyState title="No matches found" text="Try a different word or phrase." />}</section>; }
function Status({ status }) { return <span className={`status ${status}`}><span />{status}</span>; }
function Meta({ label, value }) { return <div className="meta-row"><span>{label}</span><strong>{value}</strong></div>; }
function EmptyState({ title, text }) { return <div className="empty-state"><div className="empty-icon">◌</div><h3>{title}</h3><p>{text}</p></div>; }
function ErrorBanner({ message }) { return <div className="error-banner">{message}</div>; }
function Loading() { return <div className="loading">Loading your recordings...</div>; }
function formatDuration(seconds) { if (!seconds) return "0m"; const mins = Math.floor(seconds / 60); const secs = Math.round(seconds % 60); return mins ? `${mins}m ${secs}s` : `${secs}s`; }
function formatTime(seconds) { return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`; }
function formatDate(value) { return new Date(value).toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }); }
function highlight(text) { return text; }

export default function App() { return <BrowserRouter><Layout /></BrowserRouter>; }
