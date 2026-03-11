import { useEffect, useMemo, useState } from "react";
import {
  createUser,
  ensureSession,
  getCurrentSession,
  getProfile,
  getQuestions,
  logoutSession,
  resetProfile,
  saveProfile,
  sendChat,
} from "./api";

const starterSuggestions = [
  "Schedule a meeting",
  "Schedule a birthday",
  "Schedule an event",
  "Ask me anything",
];

const mockScheduleItems = [
  { id: 1, title: "Team Meeting", time: "Today • 10:00 AM", status: "scheduled" },
  { id: 2, title: "Event", time: "Today • 3:00 PM", status: "scheduled" },
  { id: 3, title: "Mom Birthday", time: "Tomorrow • 9:00 AM", status: "pending" },
  { id: 4, title: "Project Review", time: "Mon • 11:30 AM", status: "scheduled" },
];

function MenuIcon() {
  return <span className="icon-text">☰</span>;
}

function BackIcon() {
  return <span className="icon-text">‹</span>;
}

function RefreshIcon() {
  return <span className="icon-text">◌</span>;
}

function VoiceIcon() {
  return <span className="icon-text">◉</span>;
}

function SendIcon() {
  return <span className="icon-text">➜</span>;
}

function formatLabel(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function HistoryRail({ history, activeScreen, setActiveScreen, userId }) {
  return (
    <aside className="history-rail">
      <div className="history-search-wrap">
        <input className="history-search" placeholder="Search" />
        <button className="mini-icon-btn">✎</button>
      </div>

      <div className="history-section-title">Recent chats</div>

      <div className="history-list">
        {history.length === 0 ? (
          <div className="history-empty">No conversations yet.</div>
        ) : (
          history.map((entry, index) => (
            <button
              key={`${entry.message}-${index}`}
              className="history-item"
              onClick={() => setActiveScreen("chat")}
            >
              <div className="history-item-title">{entry.message}</div>
              <div className="history-item-subtitle">
                {entry.result?.route_taken || "response"}
              </div>
            </button>
          ))
        )}
      </div>

      <div className="history-footer">
        <button className="rail-footer-btn" onClick={() => setActiveScreen("home")}>
          Home
        </button>
        <button className="rail-footer-btn" onClick={() => setActiveScreen("chat")}>
          Chat
        </button>
        <button className="rail-footer-btn" onClick={() => setActiveScreen("schedule")}>
          Schedule
        </button>

        <div className="profile-mini-card">
          <div className="profile-avatar-small">
            {(userId || "U").slice(0, 1).toUpperCase()}
          </div>
          <div>
            <div className="profile-mini-name">{userId || "loading..."}</div>
            <div className="profile-mini-sub">Authenticated session</div>
          </div>
          <div className="profile-mini-badge">v1.0</div>
        </div>
      </div>
    </aside>
  );
}

function OrbCenter({ subtitle = "Hello", title = "How can I help you today?" }) {
  return (
    <div className="orb-center-wrap">
      <div className="orb-glow"></div>
      <div className="orb-core"></div>
      <div className="orb-caption-top">{subtitle}</div>
      <div className="orb-caption-main">{title}</div>
    </div>
  );
}

function SuggestionChips({ onPick }) {
  return (
    <div className="suggestion-wrap">
      <div className="suggestion-label">Suggestions</div>
      <div className="suggestion-grid">
        {starterSuggestions.map((item) => (
          <button key={item} className="suggestion-chip" onClick={() => onPick(item)}>
            {item}
          </button>
        ))}
      </div>
    </div>
  );
}

function HomeScreen({ userId, onOpenChat, onOpenVoice, onOpenSchedule, onSuggestion }) {
  return (
    <div className="mobile-screen">
      <div className="topbar">
        <button className="icon-btn">
          <MenuIcon />
        </button>
        <div className="brand-title">Seyalvel AI</div>
        <button className="icon-btn">
          <RefreshIcon />
        </button>
      </div>

      <div className="screen-body center-layout">
        <OrbCenter subtitle={`Hello ${userId || "there"}!`} title="How can I help you today?" />
      </div>

      <div className="bottom-stack">
        <SuggestionChips onPick={onSuggestion} />

        <div className="action-row">
          <button className="ghost-pill" onClick={onOpenSchedule}>
            Schedule
          </button>
          <button className="ghost-pill" onClick={onOpenVoice}>
            Voice
          </button>
          <button className="ghost-pill" onClick={onOpenChat}>
            Chat
          </button>
        </div>
      </div>
    </div>
  );
}

function ChatScreen({ message, setMessage, onSubmit, latestResult }) {
  return (
    <div className="mobile-screen">
      <div className="topbar">
        <button className="icon-btn">
          <MenuIcon />
        </button>
        <div className="brand-title">Seyalvel AI</div>
        <button className="icon-btn">
          <RefreshIcon />
        </button>
      </div>

      <div className="screen-body">
        <div className="chat-stream">
          {latestResult ? (
            <>
              <div className="chat-bubble user">
                <div className="chat-bubble-text">Your request has been sent.</div>
              </div>

              <div className="chat-bubble ai">
                <div className="chat-bubble-title">AI Response</div>
                <div className="chat-bubble-text">{latestResult.theni_tamil_text || "-"}</div>
              </div>

              <div className="chat-meta-panel">
                <div><strong>Route:</strong> {latestResult.route_taken || "-"}</div>
                <div><strong>Risk:</strong> {latestResult.risk_level || "-"}</div>
                <div><strong>Label:</strong> {latestResult.predicted_label || "-"}</div>
              </div>
            </>
          ) : (
            <div className="empty-chat-state">
              Type a message below to begin chatting.
            </div>
          )}
        </div>
      </div>

      <form className="floating-input-wrap" onSubmit={onSubmit}>
        <input
          className="floating-input"
          placeholder="Ask me anything..."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
        <button type="submit" className="round-send-btn">
          <SendIcon />
        </button>
      </form>
    </div>
  );
}

function ScheduleScreen({ onBack }) {
  return (
    <div className="mobile-screen schedule-screen">
      <div className="topbar left-compact">
        <button className="icon-btn" onClick={onBack}>
          <BackIcon />
        </button>
        <div className="screen-title">Schedule</div>
      </div>

      <div className="schedule-filter-row">
        <button className="filter-chip active">All</button>
        <button className="filter-chip">Meetings</button>
        <button className="filter-chip">Birthdays</button>
      </div>

      <div className="schedule-card-stack">
        {mockScheduleItems.map((item) => (
          <div key={item.id} className="schedule-card">
            <div className="schedule-card-title">{item.title}</div>
            <div className="schedule-card-time">{item.time}</div>
            <div className={`status-pill ${item.status}`}>{formatLabel(item.status)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function VoiceScreen({ onBack }) {
  return (
    <div className="mobile-screen">
      <div className="topbar left-compact">
        <button className="icon-btn" onClick={onBack}>
          <BackIcon />
        </button>
        <div className="screen-title">Voice</div>
      </div>

      <div className="screen-body center-layout">
        <div className="voice-shell">
          <div className="voice-wave-ring"></div>
          <div className="voice-wave-ring ring-2"></div>
          <div className="voice-core">
            <VoiceIcon />
          </div>
          <div className="voice-label">Voice capture coming next</div>
        </div>
      </div>
    </div>
  );
}

function QuestionCard({ question, value, onChange }) {
  const { id, question_text, type, options = [] } = question;

  return (
    <div className="question-card">
      <div className="question-title">{question_text}</div>

      {type === "single" ? (
        <div className="option-grid">
          {options.map((option) => (
            <button
              key={option.value}
              className={`option-pill ${value === option.value ? "selected" : ""}`}
              onClick={() => onChange(id, option.value)}
            >
              {formatLabel(option.label || option.value)}
            </button>
          ))}
        </div>
      ) : type === "multi" ? (
        <div className="option-grid">
          {options.map((option) => {
            const selected = Array.isArray(value) && value.includes(option.value);
            return (
              <button
                key={option.value}
                className={`option-pill ${selected ? "selected" : ""}`}
                onClick={() => {
                  const current = Array.isArray(value) ? value : [];
                  const next = selected
                    ? current.filter((item) => item !== option.value)
                    : [...current, option.value];
                  onChange(id, next);
                }}
              >
                {formatLabel(option.label || option.value)}
              </button>
            );
          })}
        </div>
      ) : (
        <input
          className="text-answer-input"
          value={value || ""}
          onChange={(e) => onChange(id, e.target.value)}
          placeholder="Type your answer"
        />
      )}
    </div>
  );
}

function QuestionnairePanel({
  userId,
  profileExists,
  profileSummary,
  questions,
  answers,
  setAnswers,
  onLoadProfile,
  onSaveProfile,
  onResetProfile,
  profileLoading,
  profileSaving,
}) {
  function handleAnswerChange(id, value) {
    setAnswers((prev) => ({ ...prev, [id]: value }));
  }

  return (
    <section className="dashboard-panel">
      <div className="panel-header">
        <div>
          <div className="panel-kicker">Questionnaire</div>
          <h2>Behavior profile</h2>
          <div className="panel-sub">
            Authenticated user: <strong>{userId || "-"}</strong>
          </div>
        </div>

        <div className="panel-actions">
          <button className="primary-btn soft" onClick={onLoadProfile} disabled={profileLoading}>
            {profileLoading ? "Loading..." : "Load"}
          </button>
          <button className="primary-btn" onClick={onSaveProfile} disabled={profileSaving}>
            {profileSaving ? "Saving..." : "Save"}
          </button>
          <button className="danger-btn" onClick={onResetProfile}>
            Reset
          </button>
        </div>
      </div>

      {profileExists ? (
        <div className="profile-banner success">
          Saved profile loaded. {profileSummary ? `Summary: ${profileSummary}` : ""}
        </div>
      ) : (
        <div className="profile-banner">
          No saved profile yet for this authenticated user.
        </div>
      )}

      <div className="question-grid">
        {questions.map((question) => (
          <QuestionCard
            key={question.id}
            question={question}
            value={answers[question.id]}
            onChange={handleAnswerChange}
          />
        ))}
      </div>
    </section>
  );
}

function ResultPanel({ latestResult }) {
  return (
    <section className="dashboard-panel">
      <div className="panel-header">
        <div>
          <div className="panel-kicker">Inference</div>
          <h2>Latest output</h2>
        </div>
      </div>

      {!latestResult ? (
        <div className="empty-result-state">
          Send a message to see the pipeline output here.
        </div>
      ) : (
        <>
          <div className="result-grid">
            <div className="result-pane">
              <h3>Raw English</h3>
              <p>{latestResult.raw_english || "-"}</p>
            </div>
            <div className="result-pane">
              <h3>Remodeled English</h3>
              <p>{latestResult.remodeled_english || "-"}</p>
            </div>
            <div className="result-pane">
              <h3>Standard Tamil</h3>
              <p>{latestResult.tamil_text || "-"}</p>
            </div>
            <div className="result-pane highlight">
              <h3>Theni Tamil</h3>
              <p>{latestResult.theni_tamil_text || "-"}</p>
            </div>
          </div>

          <div className="debug-panels">
            <div className="debug-panel">
              <h4>Stage Notes</h4>
              <pre>{JSON.stringify(latestResult.stage_notes || [], null, 2)}</pre>
            </div>
            <div className="debug-panel">
              <h4>Timings</h4>
              <pre>{JSON.stringify(latestResult.timings_ms || {}, null, 2)}</pre>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

export default function App() {
  const [userId, setUserId] = useState("");
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [profile, setProfile] = useState(null);
  const [profileExists, setProfileExists] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(true);

  const [activeScreen, setActiveScreen] = useState("home");
  const [message, setMessage] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatResult, setChatResult] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    async function boot() {
      try {
        setError("");
        const session = await ensureSession();
        setUserId(session.userId);

        const [questionsRes, sessionRes] = await Promise.all([
          getQuestions(),
          getCurrentSession(),
        ]);

        setQuestions(questionsRes.questions || []);
        if (sessionRes?.userId && !userId) {
          setUserId(sessionRes.userId);
        }
      } catch (err) {
        setError(err.message || "Failed to initialize app");
      } finally {
        setSessionLoading(false);
      }
    }

    boot();
  }, []);

  async function handleStartFreshSession() {
    try {
      setError("");
      setSessionLoading(true);
      await logoutSession().catch(() => {});
      const session = await createUser();
      setUserId(session.userId);
      setProfile(null);
      setProfileExists(false);
      setAnswers({});
      setChatResult(null);
      setChatHistory([]);
      setActiveScreen("home");
    } catch (err) {
      setError(err.message || "Failed to create new session");
    } finally {
      setSessionLoading(false);
    }
  }

  async function loadProfile() {
    if (!userId.trim()) {
      setError("Authenticated user is missing");
      return;
    }

    try {
      setError("");
      setProfileLoading(true);
      const res = await getProfile(userId.trim());
      setProfileExists(res.exists);
      setProfile(res.profile || null);
      setAnswers(res.profile?.answers || {});
    } catch (err) {
      setError(err.message);
    } finally {
      setProfileLoading(false);
    }
  }

  async function handleSaveProfile() {
    if (!userId.trim()) {
      setError("Authenticated user is missing");
      return;
    }

    try {
      setError("");
      setProfileSaving(true);
      const res = await saveProfile(userId.trim(), answers);
      setProfile(res.profile);
      setProfileExists(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setProfileSaving(false);
    }
  }

  async function handleResetProfile() {
    if (!userId.trim()) {
      setError("Authenticated user is missing");
      return;
    }

    try {
      setError("");
      await resetProfile(userId.trim());
      setProfile(null);
      setProfileExists(false);
      setAnswers({});
      setChatResult(null);
      setChatHistory([]);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSendMessage(e) {
    e?.preventDefault?.();

    if (!userId.trim()) {
      setError("Authenticated user is missing");
      return;
    }

    if (!message.trim()) {
      setError("Enter a message");
      return;
    }

    try {
      setError("");
      setChatLoading(true);
      const currentMessage = message.trim();
      const res = await sendChat(userId.trim(), currentMessage);
      setChatResult(res.result);
      setChatHistory((prev) => [{ message: currentMessage, result: res.result }, ...prev]);
      setMessage("");
      setActiveScreen("chat");
    } catch (err) {
      setError(err.message);
    } finally {
      setChatLoading(false);
    }
  }

  const profileSummary = useMemo(() => {
    if (!profile) return "";
    return profile.profile_summary || "";
  }, [profile]);

  function renderPhoneScreen() {
    if (activeScreen === "chat") {
      return (
        <ChatScreen
          message={message}
          setMessage={setMessage}
          onSubmit={handleSendMessage}
          latestResult={chatResult}
        />
      );
    }

    if (activeScreen === "schedule") {
      return <ScheduleScreen onBack={() => setActiveScreen("home")} />;
    }

    if (activeScreen === "voice") {
      return <VoiceScreen onBack={() => setActiveScreen("home")} />;
    }

    return (
      <HomeScreen
        userId={userId}
        onOpenChat={() => setActiveScreen("chat")}
        onOpenVoice={() => setActiveScreen("voice")}
        onOpenSchedule={() => setActiveScreen("schedule")}
        onSuggestion={(text) => {
          setMessage(text);
          setActiveScreen("chat");
        }}
      />
    );
  }

  if (sessionLoading) {
    return (
      <div className="app-shell">
        <main className="workspace" style={{ gridTemplateColumns: "1fr" }}>
          <section className="dashboard-stage">
            <div className="dashboard-panel">
              <div className="panel-header">
                <div>
                  <div className="panel-kicker">Initializing</div>
                  <h2>Preparing authenticated session</h2>
                </div>
              </div>
              <div className="loading-banner">Starting app...</div>
            </div>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <HistoryRail
        history={chatHistory}
        activeScreen={activeScreen}
        setActiveScreen={setActiveScreen}
        userId={userId}
      />

      <main className="workspace">
        <section className="phone-stage">
          <div className="phone-frame">
            {renderPhoneScreen()}
          </div>
        </section>

        <section className="dashboard-stage">
          <div className="dashboard-topbar">
            <div>
              <div className="dashboard-kicker">Persona Tamil AI</div>
              <h1>Control Center</h1>
            </div>

            <div className="dashboard-user-input">
              <label>Authenticated User ID</label>
              <input value={userId} readOnly />
            </div>
          </div>

          <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
            <button className="primary-btn soft" onClick={handleStartFreshSession}>
              New session
            </button>
            <button
              className="danger-btn"
              onClick={async () => {
                await logoutSession();
                setUserId("");
                setProfile(null);
                setProfileExists(false);
                setAnswers({});
                setChatResult(null);
                setChatHistory([]);
                setSessionLoading(true);
                try {
                  const session = await ensureSession();
                  setUserId(session.userId);
                } catch (err) {
                  setError(err.message || "Failed to recover session");
                } finally {
                  setSessionLoading(false);
                }
              }}
            >
              Logout
            </button>
          </div>

          {error ? <div className="error-banner">{error}</div> : null}
          {chatLoading ? <div className="loading-banner">Generating response...</div> : null}

          <QuestionnairePanel
            userId={userId}
            profileExists={profileExists}
            profileSummary={profileSummary}
            questions={questions}
            answers={answers}
            setAnswers={setAnswers}
            onLoadProfile={loadProfile}
            onSaveProfile={handleSaveProfile}
            onResetProfile={handleResetProfile}
            profileLoading={profileLoading}
            profileSaving={profileSaving}
          />

          <ResultPanel latestResult={chatResult} />
        </section>
      </main>
    </div>
  );
}