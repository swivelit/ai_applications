const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const STORAGE_KEYS = {
  session: "persona_session_v2",
};

function getStoredSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.session);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function setStoredSession(session) {
  localStorage.setItem(STORAGE_KEYS.session, JSON.stringify(session));
}

function clearStoredSession() {
  localStorage.removeItem(STORAGE_KEYS.session);
}

function buildRequestId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function isExpiringSoon(iso) {
  if (!iso) return false;
  const ts = new Date(iso).getTime();
  if (!Number.isFinite(ts)) return false;
  return ts - Date.now() < 60 * 1000;
}

async function rawRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new Error(data.detail || "Request failed");
    error.status = response.status;
    error.payload = data;
    throw error;
  }

  return data;
}

export async function createUser(payload = {}) {
  const data = await rawRequest("/users", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Request-Id": buildRequestId(),
    },
    body: JSON.stringify({
      name: payload.name || "Web User",
      place: payload.place || "",
      timezone: payload.timezone || "Asia/Kolkata",
      assistant_name: payload.assistant_name || "Ellie",
    }),
  });

  const session = {
    userId: data.id,
    name: data.name,
    place: data.place,
    timezone: data.timezone,
    assistantName: data.assistant_name,
    accessToken: data.access_token,
    accessExpiresAt: data.access_expires_at,
    refreshToken: data.refresh_token,
    refreshExpiresAt: data.refresh_expires_at,
    tokenType: data.token_type || "bearer",
  };

  setStoredSession(session);
  return session;
}

export async function ensureSession() {
  let session = getStoredSession();
  if (!session?.userId || !session?.refreshToken) {
    session = await createUser();
    return session;
  }

  if (!session.accessToken || isExpiringSoon(session.accessExpiresAt)) {
    session = await refreshSession();
  }

  return session;
}

export async function refreshSession() {
  const session = getStoredSession();
  if (!session?.refreshToken) {
    clearStoredSession();
    throw new Error("No refresh token available");
  }

  const data = await rawRequest("/auth/refresh", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${session.refreshToken}`,
      "X-Request-Id": buildRequestId(),
    },
  });

  const nextSession = {
    ...session,
    userId: data.user_id || session.userId,
    accessToken: data.access_token,
    accessExpiresAt: data.access_expires_at,
    refreshToken: data.refresh_token,
    refreshExpiresAt: data.refresh_expires_at,
    tokenType: data.token_type || "bearer",
  };

  setStoredSession(nextSession);
  return nextSession;
}

export async function logoutSession() {
  const session = getStoredSession();
  try {
    if (session?.accessToken) {
      await rawRequest("/auth/logout", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
          "X-Request-Id": buildRequestId(),
        },
      });
    }
  } catch {
    // ignore logout transport errors; still clear local session
  } finally {
    clearStoredSession();
  }
}

async function authRequest(path, options = {}, retry = true) {
  let session = await ensureSession();

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${session.accessToken}`,
    "X-Request-Id": buildRequestId(),
    ...(options.headers || {}),
  };

  try {
    return await rawRequest(path, {
      ...options,
      headers,
    });
  } catch (err) {
    if (retry && (err?.status === 401 || err?.status === 403)) {
      session = await refreshSession();
      return rawRequest(path, {
        ...options,
        headers: {
          ...headers,
          Authorization: `Bearer ${session.accessToken}`,
        },
      });
    }
    throw err;
  }
}

export async function getHealth() {
  return rawRequest("/api/health", {
    headers: {
      "X-Request-Id": buildRequestId(),
    },
  });
}

export async function getQuestions() {
  return rawRequest("/api/questions", {
    headers: {
      "X-Request-Id": buildRequestId(),
    },
  });
}

export async function getProfile(userId) {
  return authRequest(`/api/profile/${encodeURIComponent(userId)}`, {
    method: "GET",
  });
}

export async function saveProfile(userId, answers) {
  return authRequest(`/api/profile/${encodeURIComponent(userId)}`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

export async function resetProfile(userId) {
  return authRequest(`/api/profile/${encodeURIComponent(userId)}/reset`, {
    method: "POST",
  });
}

export async function sendChat(userId, message) {
  return authRequest("/api/chat", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      message,
    }),
  });
}

export async function getCurrentSession() {
  return getStoredSession();
}