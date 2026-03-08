import { useEffect, useMemo, useState } from "react";
import { getProfile, getQuestions, resetProfile, saveProfile, sendChat } from "./api";

const starterSuggestions = [
  "Schedule a meeting",
  "Schedule a birthday",
  "Schedule an event",
  "Ask me anything"
];

const mockScheduleItems = [
  { id: 1, title: "Team Meeting", time: "Today • 10:00 AM", status: "scheduled" },
  { id: 2, title: "Event", time: "Today • 3:00 PM", status: "scheduled" },
  { id: 3, title: "Mom Birthday", time: "Tomorrow • 9:00 AM", status: "pending" },
  { id: 4, title: "Project Review", time: "Mon • 11:30 AM", status: "scheduled" }
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

      <div className="history-section-title">My History</div>

      <div className="history-list">
        {history.length === 0 ? (
          <div className="history-empty">No conversations yet</div>
        ) : (
          history.map((item, index) => (
            <button
              key={`${item.message}-${index}`}
              className="history-item"
              onClick={() => setActiveScreen("chat")}
            >
              <div className="history-item-title">{item.message}</div>
              <div className="history-item-subtitle">
                {(item.result?.theni_tamil_text || "").slice(0, 40) || "Recent response"}
              </div>
            </button>
          ))
        )}
      </div>

      <div className="history-footer">
        <button className="rail-footer-btn">⚙ Setting</button>
        <div className="profile-mini-card">
          <div className="profile-avatar-small">A</div>
          <div className="profile-mini-meta">
            <div className="profile-mini-name">{userId || "demo_user"}</div>
            <div className="profile-mini-sub">Voice Assistant</div>
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

      <div className="schedule-list">
        {mockScheduleItems.map((item) => (
          <div key={item.id} className="schedule-card">
            <div className="schedule-card-left">
              <div className="schedule-card-title">{item.title}</div>
              <div className="schedule-card-time">{item.time}</div>
            </div>
            <div className={`schedule-status ${item.status}`}>{item.status}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function VoiceScreen({ onBack }) {
  return (
    <div className="mobile-screen">
      <div className="topbar">
        <button className="icon-btn" onClick={onBack}>
          <BackIcon />
        </button>
        <div className="brand-title">Seyalvel AI</div>
        <button className="icon-btn">
          <RefreshIcon />
        </button>
      </div>

      <div className="screen-body center-layout voice-layout">
        <OrbCenter subtitle="" title="" />
        <div className="voice-hint">Tap here to talk</div>
      </div>

      <div className="voice-bar-wrap">
        <button className="voice-side-btn">‹</button>
        <div className="voice-waveform">
          <span></span><span></span><span></span><span></span><span></span>
          <span></span><span></span><span></span><span></span><span></span>
        </div>
        <button className="voice-side-btn">
          <VoiceIcon />
        </button>
      </div>
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
  profileSaving
}) {
  return (
    <section className="dashboard-panel">
      <div className="dashboard-panel-header">
        <h2>Profile Setup</h2>
        <div className="dashboard-panel-subtitle">
          Save the assistant behavior for each user.
        </div>
      </div>

      <div className="profile-status-row">
        <div className="profile-status-card">
          <div className="status-kicker">User</div>
          <div className="status-main">{userId}</div>
        </div>
        <div className="profile-status-card">
          <div className="status-kicker">Profile</div>
          <div className="status-main">{profileExists ? "Saved" : "Not saved"}</div>
        </div>
      </div>

      <div className="panel-actions">
        <button className="dashboard-btn secondary" onClick={onLoadProfile} disabled={profileLoading}>
          {profileLoading ? "Loading..." : "Load Profile"}
        </button>
        <button className="dashboard-btn primary" onClick={onSaveProfile} disabled={profileSaving}>
          {profileSaving ? "Saving..." : "Save Profile"}
        </button>
        <button className="dashboard-btn danger" onClick={onResetProfile}>
          Reset
        </button>
      </div>

      {profileSummary ? <div className="summary-panel">{profileSummary}</div> : null}

      <div className="questions-grid">
        {questions.map((question) => {
          const value = answers[question.id];

          if (question.type === "single") {
            return (
              <div className="question-box" key={question.id}>
                <div className="question-label">{question.prompt}</div>
                <select
                  className="dashboard-select"
                  value={value || ""}
                  onChange={(e) =>
                    setAnswers((prev) => ({
                      ...prev,
                      [question.id]: e.target.value
                    }))
                  }
                >
                  <option value="">Select</option>
                  {question.options.map((option) => (
                    <option key={option} value={option}>
                      {formatLabel(option)}
                    </option>
                  ))}
                </select>
              </div>
            );
          }

          const selected = Array.isArray(value) ? value : [];

          return (
            <div className="question-box" key={question.id}>
              <div className="question-label">{question.prompt}</div>
              <div className="multi-options">
                {question.options.map((option) => {
                  const checked = selected.includes(option);
                  return (
                    <label className={`multi-chip ${checked ? "checked" : ""}`} key={option}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => {
                          let next = [...selected];

                          if (e.target.checked) {
                            if (!next.includes(option)) next.push(option);
                          } else {
                            next = next.filter((item) => item !== option);
                          }

                          if (question.max_choices && next.length > question.max_choices) {
                            next = next.slice(0, question.max_choices);
                          }

                          if (next.includes("none") && next.length > 1) {
                            next = ["none"];
                          }

                          setAnswers((prev) => ({
                            ...prev,
                            [question.id]: next
                          }));
                        }}
                      />
                      <span>{formatLabel(option)}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ResultPanel({ latestResult }) {
  if (!latestResult) {
    return (
      <section className="dashboard-panel">
        <div className="dashboard-panel-header">
          <h2>Latest Result</h2>
          <div className="dashboard-panel-subtitle">
            The newest pipeline output will appear here.
          </div>
        </div>
        <div className="empty-results">No response yet.</div>
      </section>
    );
  }

  return (
    <section className="dashboard-panel">
      <div className="dashboard-panel-header">
        <h2>Latest Result</h2>
        <div className="dashboard-panel-subtitle">
          Backend response from your persona pipeline.
        </div>
      </div>

      <div className="result-stat-grid">
        <div className="result-stat"><span>Route</span><strong>{latestResult.route_taken || "-"}</strong></div>
        <div className="result-stat"><span>Risk</span><strong>{latestResult.risk_level || "-"}</strong></div>
        <div className="result-stat"><span>Label</span><strong>{latestResult.predicted_label || "-"}</strong></div>
        <div className="result-stat"><span>Cache</span><strong>{String(latestResult.cache_hit || "-")}</strong></div>
      </div>

      <div className="result-cards">
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
    </section>
  );
}

export default function App() {
  const [userId, setUserId] = useState("demo_user");
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [profile, setProfile] = useState(null);
  const [profileExists, setProfileExists] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);

  const [activeScreen, setActiveScreen] = useState("home");
  const [message, setMessage] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatResult, setChatResult] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadQuestions() {
      try {
        const res = await getQuestions();
        setQuestions(res.questions || []);
      } catch (err) {
        setError(err.message);
      }
    }
    loadQuestions();
  }, []);

  async function loadProfile() {
    if (!userId.trim()) {
      setError("Enter a user id first");
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
      setError("Enter a user id first");
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
      setError("Enter a user id first");
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
      setError("Enter a user id first");
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
              <label>User ID</label>
              <input
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="demo_user"
              />
            </div>
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