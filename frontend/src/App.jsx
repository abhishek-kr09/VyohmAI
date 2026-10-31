import { useEffect, useMemo, useRef, useState } from "react";
import { BrowserRouter, Link, NavLink, Route, Routes, useNavigate, useParams, useSearchParams } from "react-router-dom";
import api from "./services/api";
import "./index.css";

const navItems = [
  { to: "/", label: "Overview", icon: "⌂", end: true },
  { to: "/sessions", label: "Sessions", icon: "◉" },
  { to: "/assistant", label: "AI Assistant", icon: "✦" },
  { to: "/actions", label: "Actions", icon: "✓" },
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
        <div className="page-container"><Routes><Route path="/" element={<Dashboard />} /><Route path="/sessions" element={<Sessions />} /><Route path="/sessions/:recordingId" element={<RecordingDetails />} /><Route path="/recordings" element={<Sessions />} /><Route path="/recordings/:recordingId" element={<RecordingDetails />} /><Route path="/assistant" element={<Assistant />} /><Route path="/actions" element={<Actions />} /><Route path="/insights" element={<Sessions />} /></Routes></div>
      </main>
    </div>
  );
}

function Dashboard() {
  const [recordings, setRecordings] = useState([]);
  const [events, setEvents] = useState([]);
  const [deletingId, setDeletingId] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = () => {
      api.get("/actions/calendar-events").then((response) => { if (active) setEvents(response.data); }).catch(() => {});
      return api.get("/recordings").then((response) => { if (active) { setRecordings(response.data); setError(""); } }).catch(() => { if (active) setError("Could not load recordings. Is the backend running?"); });
    };
    load();
    const timer = setInterval(load, 5000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  const totalSeconds = recordings.reduce((sum, item) => sum + item.duration_ms / 1000, 0);
  const completed = recordings.filter((item) => item.status === "completed").length;
  return <><PageHeading eyebrow="YOUR WORKSPACE" title="Good morning, Abhishek" subtitle="Here's what's happening with your sessions." action={<Link className="primary-button" to="/sessions">View sessions <span>→</span></Link>} />
    {error && <ErrorBanner message={error} />}
    <div className="stat-grid"><Stat label="Total sessions" value={recordings.length} detail="All time" icon="◉" /><Stat label="Total duration" value={formatDuration(totalSeconds)} detail="Across all sessions" icon="◷" /><Stat label="Transcribed" value={`${completed}/${recordings.length}`} detail="Ready to review" icon="✓" /></div>
    <section className="content-card recent-card"><div className="section-heading"><div><h2>Recent sessions</h2><p>Your latest conversations, all in one place.</p></div><Link to="/sessions" className="text-link">View all <span>→</span></Link></div>{recordings.length === 0 ? <EmptyState title="No sessions yet" text="Start a session on the device to build your knowledge base." /> : <RecordingTable recordings={recordings.slice(0, 5)} />}</section>
        <CalendarView events={events} deletingId={deletingId} onDelete={async (eventId) => {
          if (!window.confirm("Delete this calendar event?")) return;
          setDeletingId(eventId);
          try {
            await api.delete(`/actions/calendar-events/${eventId}`);
            setEvents((items) => items.filter((item) => item.id !== eventId));
          } catch (requestError) {
            if (requestError.response?.status === 404) setEvents((items) => items.filter((item) => item.id !== eventId));
            else setError(requestError.response?.data?.detail || "Could not delete the calendar event.");
          } finally { setDeletingId(null); }
        }} />
      </>;
}

function SessionsLegacy() {
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
  return <><PageHeading eyebrow="SESSIONS" title="Sessions" subtitle="Review, search, and revisit every conversation." />{error && <ErrorBanner message={error} />}<div className="search-wrap"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search sessions, names, or topics..." /><kbd>⌘ K</kbd></div>{results ? <SearchResults results={results} /> : loading ? <Loading /> : <section className="content-card"><div className="section-heading"><div><h2>All sessions</h2><p>{recordings.length} session{recordings.length === 1 ? "" : "s"} · updates automatically</p></div></div><RecordingTable recordings={recordings} /></section>}</>;
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
  return <><Link className="back-link" to="/sessions">← Back to sessions</Link><PageHeading eyebrow="SESSION" title={recording.insight?.topic || recording.filename} subtitle={`${formatDate(recording.recorded_at)} · ${recording.device_id}`} /><div className="insights-section"><div className="eyebrow">INSIGHTS</div><InsightPanel recording={recording} />{recording.status === "completed" && <SessionAgentActions recordingId={recording.id} />}</div><div className="detail-layout"><section className="content-card transcript-card"><div className="section-heading"><div><h2>Transcript</h2><p>{recording.transcript.length} timestamped segments{recording.status === "processing" ? " · updating automatically" : ""}</p></div><Status status={recording.status} /></div><audio ref={audioRef} controls className="audio-player" src={`${api.defaults.baseURL}/recordings/${recording.id}/audio`} />{recording.transcript.length ? <div className="transcript-list">{recording.transcript.map((segment) => <button className="transcript-row" key={segment.id} onClick={() => seek(segment.start_time)}><span className="timestamp">{formatTime(segment.start_time)}</span><span>{segment.text}</span></button>)}</div> : <EmptyState title="Transcript not available" text={recording.status === "failed" ? "Transcription failed. Retry it below." : "This session is still being processed. This page checks for updates automatically."} />}{recording.status === "failed" && <button className="primary-button retry-button" onClick={retry}>Retry transcription <span>↻</span></button>}</section></div></>;
}

function InsightPanel({ recording }) {
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState("");
  const [runningItemId, setRunningItemId] = useState(null);
  const [agentMessage, setAgentMessage] = useState("");
  const [pendingPlan, setPendingPlan] = useState(null);
  const [completedIds, setCompletedIds] = useState([]);
  const runActionItem = async (itemId) => {
    setError("");
    setAgentMessage("");
    setPendingPlan(null);
    setRunningItemId(itemId);
    try {
      const result = await api.post(`/actions/items/${itemId}/run`);
      if (result.data.requires_confirmation) setPendingPlan({ ...result.data, itemId });
      else setAgentMessage(result.data.message);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "The agent could not perform this action.");
    } finally {
      setRunningItemId(null);
    }
  };
  const confirmPlan = async (plan) => {
    setError("");
    try {
      const result = await api.post("/actions/agent/confirm", { plan, recording_id: pendingPlan.recording_id });
      setAgentMessage(result.data.message);
      if (result.data.action_type === "complete_action") setCompletedIds((ids) => [...ids, pendingPlan.itemId]);
      setPendingPlan(null);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "The agent could not perform this action.");
    }
  };
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
    return <section className="content-card insight-panel"><div className="assistant-icon">✦</div><h2>Understand this session</h2><p>Generate a grounded summary, people, meetings, and action items from the transcript.</p><div className="session-meta-grid"><Meta label="Recorded" value={formatDate(recording.recorded_at)} /><Meta label="Duration" value={formatDuration(recording.duration_ms / 1000)} /><Meta label="Device" value={recording.device_id} /><Meta label="Battery" value={recording.battery_pct == null ? "USB powered" : `${recording.battery_pct}%`} /></div>{error && <div className="error-banner">{error}</div>}<button className="primary-button" onClick={generate} disabled={extracting}>{extracting ? "Generating..." : "Generate insights"} {!extracting && <span>→</span>}</button></section>;
  }
  if (!recording.insight) return null;
  return <section className="content-card insight-panel"><div className="section-heading"><div><h2>Session intelligence</h2><p>Everything extracted from this session.</p></div><span className="status completed"><span />ready</span></div><div className="session-meta-grid"><Meta label="Recorded" value={formatDate(recording.recorded_at)} /><Meta label="Duration" value={formatDuration(recording.duration_ms / 1000)} /><Meta label="Device" value={recording.device_id} /><Meta label="Battery" value={recording.battery_pct == null ? "USB powered" : `${recording.battery_pct}%`} /></div>{recording.insight.topic && <div className="insight-summary"><strong>Topic</strong><p>{recording.insight.topic}</p></div>}{recording.insight.summary && <p className="insight-summary"><strong>Summary</strong><br />{recording.insight.summary}</p>}<div className="insight-columns"><div><h3>Important highlights</h3>{recording.insight.highlights.length ? <ul className="insight-list">{recording.insight.highlights.map((highlight, index) => <li key={index}>{highlight}</li>)}</ul> : <p className="muted">No highlights identified.</p>}</div><div><h3>People and meetings</h3>{recording.insight.people.length ? recording.insight.people.map((person) => <div className="insight-item" key={person.name}><strong>{person.name}</strong><span>{person.role || "Mentioned in session"}</span></div>) : <p className="muted">No people identified.</p>}{recording.insight.meetings.length ? recording.insight.meetings.map((meeting, index) => <div className="insight-item" key={index}><strong>{meeting.purpose || "Meeting"}</strong><span>{meeting.date || ""} {meeting.time || ""}</span></div>) : null}</div><div><h3>Action items</h3>{pendingPlan && <AgentPlanReview pending={pendingPlan} onConfirm={confirmPlan} onCancel={() => setPendingPlan(null)} />}{agentMessage && <p className="success-text">{agentMessage}</p>}{error && <div className="error-banner">{error}</div>}{recording.action_items.length ? recording.action_items.map((item) => {
    const completed = item.status === "completed" || completedIds.includes(item.id);
    return <div className="insight-item insight-action-item" key={item.id}>
      <div><strong>{item.task}</strong><span>{item.person || "Owner not specified"}{item.due_date ? ` · Due ${formatDate(item.due_date)}` : ""}</span></div>
      {completed ? <span className="status completed"><span />done</span> : <button className="run-agent-button" onClick={() => runActionItem(item.id)} disabled={runningItemId !== null}>{runningItemId === item.id ? "Running..." : "Run agent ✦"}</button>}
    </div>;
  }) : <p className="muted">No action items identified.</p>}</div></div></section>;
}

function Assistant() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const sessionId = searchParams.get("recording_id");
  const [sessions, setSessions] = useState([]);
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const suggestions = ["What did I promise?", "Show my pending tasks", "Find vendor discussions"];
  useEffect(() => {
    api.get("/recordings/insights").then((result) => setSessions(result.data)).catch(() => setError("Could not load sessions."));
  }, []);
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
      <div className="session-context"><label htmlFor="assistant-session">Session context</label><select id="assistant-session" value={sessionId || ""} onChange={(event) => navigate(event.target.value ? `/assistant?recording_id=${event.target.value}` : "/assistant")}><option value="">All sessions</option>{sessions.map((session) => <option value={session.recording_id} key={session.recording_id}>{session.insight?.topic || session.session_name}</option>)}</select>{sessionId && <Link className="secondary-button" to={`/sessions/${sessionId}`}>View insights <span>→</span></Link>}</div>
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
  const [dailyActions, setDailyActions] = useState([]);
  const [sessionFilter, setSessionFilter] = useState("");
  const [runningItemId, setRunningItemId] = useState(null);
  const [itemAgentMessage, setItemAgentMessage] = useState("");
  const [itemPlan, setItemPlan] = useState(null);
  const [instruction, setInstruction] = useState("");
  const [agentMessage, setAgentMessage] = useState("");
  const [agentPlan, setAgentPlan] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [calendar, setCalendar] = useState({ title: "", description: "", start_time: "", end_time: "", attendees: "", source_recording_id: "" });
  const [email, setEmail] = useState({ recipient: "", subject: "", body: "", source_recording_id: "" });
  const [calendarPreview, setCalendarPreview] = useState(null);
  const [emailPreview, setEmailPreview] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api.get("/recordings"), api.get("/actions/calendar-events"), api.get("/actions/email-drafts"), api.get("/actions/daily")])
      .then(([recordingResult, eventResult, draftResult, dailyResult]) => {
        setRecordings(recordingResult.data);
        setEvents(eventResult.data);
        setDrafts(draftResult.data);
        setDailyActions(dailyResult.data);
      })
      .catch(() => setError("Could not load saved actions."));
  }, []);
  const refreshActions = async () => {
    const [eventResult, draftResult, dailyResult] = await Promise.all([
      api.get("/actions/calendar-events"),
      api.get("/actions/email-drafts"),
      api.get("/actions/daily"),
    ]);
    setEvents(eventResult.data);
    setDrafts(draftResult.data);
    setDailyActions(dailyResult.data);
  };
  const runActionItem = async (itemId) => {
    setError("");
    setItemAgentMessage("");
    setItemPlan(null);
    setRunningItemId(itemId);
    try {
      const result = await api.post(`/actions/items/${itemId}/run`);
      if (result.data.requires_confirmation) setItemPlan(result.data);
      else setItemAgentMessage(result.data.message);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "The agent could not perform this action.");
    } finally {
      setRunningItemId(null);
    }
  };
  const confirmItemPlan = async (plan) => {
    setError("");
    try {
      const result = await api.post("/actions/agent/confirm", { plan, recording_id: itemPlan.recording_id });
      setItemAgentMessage(result.data.message);
      setItemPlan(null);
      await refreshActions();
    } catch (requestError) { setError(requestError.response?.data?.detail || "The agent could not perform this action."); }
  };
  const runAgent = async (event) => {
    event.preventDefault();
    setError("");
    setAgentMessage("");
    setAgentPlan(null);
    try {
      const result = await api.post("/actions/agent", { instruction, recording_id: null });
      if (result.data.requires_confirmation) setAgentPlan(result.data);
      else setAgentMessage(result.data.message);
    } catch (requestError) { setError(requestError.response?.data?.detail || "The action agent could not complete that instruction."); }
  };
  const confirmAgentPlan = async (plan) => {
    setError("");
    try {
      const result = await api.post("/actions/agent/confirm", { plan, recording_id: agentPlan.recording_id });
      setAgentMessage(result.data.message);
      setAgentPlan(null);
      setInstruction("");
      await refreshActions();
    } catch (requestError) { setError(requestError.response?.data?.detail || "The action agent could not complete that instruction."); }
  };
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
  const removeItem = async (url, id, setItems, label) => {
    if (!window.confirm(`Delete this ${label}?`)) return;
    setError("");
    setDeletingId(id);
    try {
      await api.delete(url);
      setItems((items) => items.filter((item) => item.id !== id));
    } catch (requestError) {
      if (requestError.response?.status === 404) setItems((items) => items.filter((item) => item.id !== id));
      else setError(requestError.response?.data?.detail || `Could not delete the ${label}.`);
    } finally {
      setDeletingId(null);
    }
  };
  const deleteEvent = (eventId) => removeItem(`/actions/calendar-events/${eventId}`, eventId, setEvents, "calendar event");
  const deleteDraft = (draftId) => removeItem(`/actions/email-drafts/${draftId}`, draftId, setDrafts, "email draft");
  return <><PageHeading eyebrow="ACTIONS" title="Turn insights into action" subtitle="Give the action agent an instruction. It uses extracted session actions to create local events, save drafts, or complete tasks." />{error && <ErrorBanner message={error} />}
    <section className="content-card action-card agent-command"><div className="section-heading"><div><h2>Action agent</h2><p>Examples: “Schedule the vendor follow-up tomorrow at 10 AM” or “Draft a follow-up email.”</p></div><span className="action-badge">AGENT</span></div><form className="action-form" onSubmit={runAgent}><textarea required minLength="2" maxLength="1000" value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="Tell the agent what to do..." /><button className="primary-button">Run agent <span>→</span></button></form>{agentPlan && <AgentPlanReview pending={agentPlan} onConfirm={confirmAgentPlan} onCancel={() => setAgentPlan(null)} />}{agentMessage && <p className="success-text">{agentMessage}</p>}</section>
    <ActionQueue
      dailyActions={dailyActions}
      sessionFilter={sessionFilter}
      onSessionFilterChange={setSessionFilter}
      runningItemId={runningItemId}
      onRunItem={runActionItem}
      message={itemAgentMessage}
      pendingPlan={itemPlan}
      onConfirmPlan={confirmItemPlan}
      onCancelPlan={() => setItemPlan(null)}
    />
    <div className="actions-grid">
      <section className="content-card action-card"><div className="section-heading"><div><h2>Calendar event</h2><p>Create a local event after confirmation.</p></div><span className="action-badge">CONFIRM</span></div><form className="action-form" onSubmit={previewEvent}><input required placeholder="Event title" value={calendar.title} onChange={(event) => setCalendar({ ...calendar, title: event.target.value })} /><textarea placeholder="Description" value={calendar.description} onChange={(event) => setCalendar({ ...calendar, description: event.target.value })} /><div className="form-row"><label>Start<input required type="datetime-local" value={calendar.start_time} onChange={(event) => setCalendar({ ...calendar, start_time: event.target.value })} /></label><label>End<input required type="datetime-local" value={calendar.end_time} onChange={(event) => setCalendar({ ...calendar, end_time: event.target.value })} /></label></div><input placeholder="Attendees (comma-separated emails)" value={calendar.attendees} onChange={(event) => setCalendar({ ...calendar, attendees: event.target.value })} /><select value={calendar.source_recording_id} onChange={(event) => setCalendar({ ...calendar, source_recording_id: event.target.value })}><option value="">Source recording (optional)</option>{recordings.map((recording) => <option value={recording.id} key={recording.id}>{recording.filename}</option>)}</select><button className="primary-button">Preview event <span>→</span></button></form>{calendarPreview && <Confirmation title="Confirm calendar event" text={`${calendarPreview.title} · ${formatDate(calendarPreview.start_time)}`} onConfirm={confirmEvent} onCancel={() => setCalendarPreview(null)} />}</section>
      <section className="content-card action-card"><div className="section-heading"><div><h2>Email draft</h2><p>Save a draft for review. Nothing is sent.</p></div><span className="action-badge">DRAFT</span></div><form className="action-form" onSubmit={previewEmail}><input required type="email" placeholder="Recipient email" value={email.recipient} onChange={(event) => setEmail({ ...email, recipient: event.target.value })} /><input required placeholder="Subject" value={email.subject} onChange={(event) => setEmail({ ...email, subject: event.target.value })} /><textarea required rows="5" placeholder="Email body" value={email.body} onChange={(event) => setEmail({ ...email, body: event.target.value })} /><select value={email.source_recording_id} onChange={(event) => setEmail({ ...email, source_recording_id: event.target.value })}><option value="">Source recording (optional)</option>{recordings.map((recording) => <option value={recording.id} key={recording.id}>{recording.filename}</option>)}</select><button className="primary-button">Preview draft <span>→</span></button></form>{emailPreview && <Confirmation title="Save this email draft?" text={`${emailPreview.recipient} · ${emailPreview.subject}`} onConfirm={confirmEmail} onCancel={() => setEmailPreview(null)} />}</section>
    </div>
    <div className="saved-actions"><CalendarView events={events} onDelete={deleteEvent} deletingId={deletingId} /><section className="content-card saved-card"><div className="section-heading"><div><h2>Email drafts</h2><p>{drafts.length} saved draft{drafts.length === 1 ? "" : "s"} · never sent</p></div></div>{drafts.length ? drafts.map((draft) => <details className="draft-item" key={draft.id}><summary><div><strong>{draft.subject}</strong><span>To {draft.recipient} · {draft.status} · {formatDate(draft.created_at)}</span></div><button type="button" className="delete-button" disabled={deletingId === draft.id} onClick={(event) => { event.preventDefault(); event.stopPropagation(); deleteDraft(draft.id); }}>{deletingId === draft.id ? "Deleting..." : "Delete"}</button></summary><pre className="draft-body">{draft.body}</pre><div className="session-tools"><button className="secondary-button" onClick={() => navigator.clipboard?.writeText(`To: ${draft.recipient}\nSubject: ${draft.subject}\n\n${draft.body}`)}>Copy draft</button>{draft.source_recording_id && <Link className="text-link" to={`/sessions/${draft.source_recording_id}`}>Source session →</Link>}</div></details>) : <p className="muted">No email drafts yet.</p>}</section></div>
  </>;
}

function ActionQueue({ dailyActions, sessionFilter, onSessionFilterChange, runningItemId, onRunItem, message, pendingPlan, onConfirmPlan, onCancelPlan }) {
  const sessions = useMemo(() => {
    const seen = new Map();
    dailyActions.forEach((item) => { if (!seen.has(item.recording_id)) seen.set(item.recording_id, item.recording_name); });
    return [...seen.entries()].map(([id, name]) => ({ id, name }));
  }, [dailyActions]);
  const visible = sessionFilter ? dailyActions.filter((item) => item.recording_id === sessionFilter) : dailyActions;
  return <section className="content-card saved-card">
    <div className="section-heading">
      <div><h2>Today’s action queue</h2><p>{visible.length} pending agent action{visible.length === 1 ? "" : "s"}{sessionFilter ? " in this session" : ""} · run any action with one click</p></div>
      <select className="session-filter" value={sessionFilter} onChange={(event) => onSessionFilterChange(event.target.value)}>
        <option value="">All sessions</option>
        {sessions.map((session) => <option value={session.id} key={session.id}>{session.name}</option>)}
      </select>
    </div>
    {pendingPlan && <AgentPlanReview pending={pendingPlan} onConfirm={onConfirmPlan} onCancel={onCancelPlan} />}
    {message && <p className="success-text">{message}</p>}
    {visible.length ? visible.map((item) => <div className="saved-item" key={item.id}>
      <div><strong>{item.task}</strong><span>{item.person || "Unassigned"} · {item.due_date ? formatDate(item.due_date) : "No due date"} · {item.recording_name}</span></div>
      <button className="run-agent-button" onClick={() => onRunItem(item.id)} disabled={runningItemId !== null}>
        {runningItemId === item.id ? "Running..." : "Run agent ✦"}
      </button>
    </div>) : <p className="muted">{sessionFilter ? "No pending actions for this session." : "No pending actions from your sessions."}</p>}
  </section>;
}

function Sessions() {
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
  return <><PageHeading eyebrow="WORKSPACE" title="Sessions" subtitle="Every session includes its transcript, insights, action items, and grounded assistant." />{error && <ErrorBanner message={error} />}{!sessions.length ? <section className="content-card"><EmptyState title="No sessions yet" text="Start a session on the device and it will appear here after Wi-Fi upload." /></section> : <div className="insights-groups">{Object.entries(groups).map(([date, items]) => <section className="insight-date-group" key={date}><h2>{date}</h2><div className="session-list">{items.map((session) => <Link className="session-card content-card session-link-card" to={`/sessions/${session.recording_id}`} key={session.recording_id}><div className="session-header"><div className="session-icon">✦</div><div><strong>{session.insight?.topic || session.session_name}</strong><span>{formatTime(Math.max(0, session.duration_ms / 1000))} · {session.status}</span></div><span className="session-chevron">›</span></div><div className="session-summary">{session.insight?.summary || "Insights are being prepared. Open the session to view its transcript and status."}<div className="session-tags"><span>{session.insight ? `${session.insight.highlights.length} highlights` : "Processing"}</span><span>{session.action_items.length} action items</span></div></div></Link>)}</div></section>)}</div>}</>;
}

function toLocalInput(value) {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function AgentPlanReview({ pending, onConfirm, onCancel }) {
  const [plan, setPlan] = useState(pending.plan);
  const [busy, setBusy] = useState(false);
  useEffect(() => setPlan(pending.plan), [pending]);
  const set = (key) => (event) => setPlan({ ...plan, [key]: event.target.value });
  const submit = async () => {
    setBusy(true);
    const payload = { ...plan };
    if (plan.action_type === "create_calendar") {
      payload.start_time = plan.start_time ? new Date(plan.start_time).toISOString() : null;
      payload.end_time = plan.end_time ? new Date(plan.end_time).toISOString() : null;
      payload.attendees = (Array.isArray(plan.attendees) ? plan.attendees : String(plan.attendees || "").split(",")).map((item) => item.trim()).filter(Boolean);
    }
    try { await onConfirm(payload); } finally { setBusy(false); }
  };
  const title = { create_calendar: "Agent wants to add a calendar event", create_email: "Agent wants to save an email draft", complete_action: "Agent wants to mark an action complete" }[plan.action_type] || "Agent action";
  return <div className="plan-review">
    <div className="plan-review-head"><span className="action-badge">CONFIRM</span><strong>{title}</strong></div>
    <p>{pending.message} Review and edit before confirming — nothing happens until you confirm.</p>
    {plan.action_type === "create_calendar" && <div className="action-form">
      <input value={plan.title || ""} onChange={set("title")} placeholder="Event title" />
      <textarea value={plan.description || ""} onChange={set("description")} placeholder="Description" />
      <div className="form-row"><label>Start<input type="datetime-local" value={toLocalInput(plan.start_time)} onChange={(event) => setPlan({ ...plan, start_time: event.target.value })} /></label><label>End<input type="datetime-local" value={toLocalInput(plan.end_time)} onChange={(event) => setPlan({ ...plan, end_time: event.target.value })} /></label></div>
      <input value={Array.isArray(plan.attendees) ? plan.attendees.join(", ") : plan.attendees || ""} onChange={set("attendees")} placeholder="Attendees (comma-separated emails)" />
    </div>}
    {plan.action_type === "create_email" && <div className="action-form">
      <input value={plan.recipient || ""} onChange={set("recipient")} placeholder="Recipient email" />
      <input value={plan.subject || ""} onChange={set("subject")} placeholder="Subject" />
      <textarea rows="7" value={plan.body || ""} onChange={set("body")} placeholder="Body" />
      <small className="muted">Saved as a draft only. It is never sent.</small>
    </div>}
    <div className="plan-review-actions"><button className="secondary-button" onClick={onCancel} disabled={busy}>Cancel</button><button className="primary-button" onClick={submit} disabled={busy}>{busy ? "Saving..." : "Confirm"}</button></div>
  </div>;
}

function CalendarView({ events, onDelete, deletingId }) {
  const now = new Date();
  const sorted = [...events].sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
  const upcoming = sorted.filter((event) => new Date(event.end_time) >= now);
  const past = sorted.filter((event) => new Date(event.end_time) < now).reverse();
  const renderEvent = (event) => {
    const start = new Date(event.start_time);
    return <div className="event-date-item" key={event.id}>
      <div className="event-date-badge"><span>{start.toLocaleDateString(undefined, { month: "short" })}</span><strong>{start.getDate()}</strong><small>{start.toLocaleDateString(undefined, { weekday: "short" })}</small></div>
      <div className="event-date-info"><strong>{event.title}</strong><span>{start.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })} – {new Date(event.end_time).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}{event.attendees.length ? ` · ${event.attendees.join(", ")}` : ""}</span>{event.source_recording_id && <Link className="text-link" to={`/sessions/${event.source_recording_id}`}>Source session →</Link>}</div>
      {onDelete && <button type="button" className="delete-button" disabled={deletingId === event.id} onClick={() => onDelete(event.id)}>{deletingId === event.id ? "Deleting..." : "Delete"}</button>}
    </div>;
  };
  return <section className="content-card saved-card calendar-card">
    <div className="section-heading"><div><h2>Calendar</h2><p>{upcoming.length} upcoming · {past.length} past</p></div></div>
    {!events.length && <p className="muted">No calendar events yet.</p>}
    {upcoming.map(renderEvent)}
    {past.length > 0 && <><h3 className="event-date-group">Past</h3>{past.map(renderEvent)}</>}
  </section>;
}

function SessionAgentActions({ recordingId }) {
  const [busy, setBusy] = useState("");
  const [pending, setPending] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const ask = async (kind, instruction) => {
    setBusy(kind); setError(""); setMessage(""); setPending(null);
    try {
      const result = await api.post("/actions/agent", { instruction, recording_id: recordingId });
      if (result.data.requires_confirmation) setPending(result.data); else setMessage(result.data.message);
    } catch (requestError) { setError(requestError.response?.data?.detail || "The agent could not prepare that action."); }
    finally { setBusy(""); }
  };
  const confirm = async (plan) => {
    setError("");
    try {
      const result = await api.post("/actions/agent/confirm", { plan, recording_id: pending.recording_id });
      setMessage(result.data.message); setPending(null);
    } catch (requestError) { setError(requestError.response?.data?.detail || "The agent could not complete that action."); }
  };
  return <section className="content-card session-agent-card">
    <div className="section-heading"><div><h2>Act on this session</h2><p>The agent prepares the action from this session and asks you to confirm before saving.</p></div><span className="action-badge">AGENT</span></div>
    <div className="session-tools">
      <button className="primary-button" disabled={!!busy} onClick={() => ask("calendar", "Add the next meeting or follow-up mentioned in this session to my calendar.")}>{busy === "calendar" ? "Preparing..." : "Add meeting to calendar"}</button>
      <button className="secondary-button" disabled={!!busy} onClick={() => ask("email", "Draft a follow-up email summarizing this session's decisions and action items for the main external participant.")}>{busy === "email" ? "Preparing..." : "Draft follow-up email"}</button>
    </div>
    {pending && <AgentPlanReview pending={pending} onConfirm={confirm} onCancel={() => setPending(null)} />}
    {message && <p className="success-text">{message} <Link className="text-link" to="/actions">View in Actions →</Link></p>}
    {error && <div className="error-banner">{error}</div>}
  </section>;
}

function Confirmation({ title, text, onConfirm, onCancel }) {
  return <div className="confirmation"><div><strong>{title}</strong><span>{text}</span></div><div><button className="secondary-button" onClick={onCancel}>Cancel</button><button className="primary-button" onClick={onConfirm}>Confirm</button></div></div>;
}

function PageHeading({ eyebrow, title, subtitle, action }) { return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>; }
function Stat({ label, value, detail, icon }) { return <div className="stat-card"><div className="stat-icon">{icon}</div><div><p>{label}</p><strong>{value}</strong><small>{detail}</small></div></div>; }
function RecordingTable({ recordings }) { return <div className="recording-list">{recordings.map((recording) => <Link className="recording-item" to={`/sessions/${recording.id}`} key={recording.id}><div className="recording-icon">♫</div><div className="recording-info"><strong>{recording.filename}</strong><span>{formatDate(recording.recorded_at)} · {recording.device_id}</span></div><span className="recording-duration">{formatDuration(recording.duration_ms / 1000)}</span><Status status={recording.status} /><span className="chevron">›</span></Link>)}</div>; }
function SearchResults({ results }) { return <section className="content-card"><div className="section-heading"><div><h2>Search results</h2><p>{results.length} matching transcript segment{results.length === 1 ? "" : "s"}</p></div></div>{results.length ? <div className="search-results">{results.map((result, index) => <Link to={`/sessions/${result.recording_id}`} className="result-item" key={`${result.recording_id}-${index}`}><div><strong>{result.recording_name}</strong><span>{formatDate(result.recorded_at)} · {formatTime(result.start_time)}</span></div><p>{highlight(result.text)}</p></Link>)}</div> : <EmptyState title="No matches found" text="Try a different word or phrase." />}</section>; }
function Status({ status }) { return <span className={`status ${status}`}><span />{status}</span>; }
function Meta({ label, value }) { return <div className="meta-row"><span>{label}</span><strong>{value}</strong></div>; }
function EmptyState({ title, text }) { return <div className="empty-state"><div className="empty-icon">◌</div><h3>{title}</h3><p>{text}</p></div>; }
function ErrorBanner({ message }) { return <div className="error-banner">{message}</div>; }
function Loading() { return <div className="loading">Loading your sessions...</div>; }
function formatDuration(seconds) { if (!seconds) return "0m"; const mins = Math.floor(seconds / 60); const secs = Math.round(seconds % 60); return mins ? `${mins}m ${secs}s` : `${secs}s`; }
function formatTime(seconds) { return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`; }
function formatDate(value) { return new Date(value).toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }); }
function highlight(text) { return text; }

export default function App() { return <BrowserRouter><Layout /></BrowserRouter>; }
