const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json"
    },
    ...options
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }

  return data;
}

export async function getHealth() {
  return request("/api/health");
}

export async function getQuestions() {
  return request("/api/questions");
}

export async function getProfile(userId) {
  return request(`/api/profile/${encodeURIComponent(userId)}`);
}

export async function saveProfile(userId, answers) {
  return request(`/api/profile/${encodeURIComponent(userId)}`, {
    method: "POST",
    body: JSON.stringify({ answers })
  });
}

export async function resetProfile(userId) {
  return request(`/api/profile/${encodeURIComponent(userId)}/reset`, {
    method: "POST"
  });
}

export async function sendChat(userId, message) {
  return request("/api/chat", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      message
    })
  });
}