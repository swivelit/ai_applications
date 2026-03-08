import Constants from "expo-constants";
import {
  getStoredAccessToken,
  getStoredTokenMeta,
  setStoredAccessToken,
  setStoredTokenMeta,
  clearAllStoredAuth,
} from "./storage";

const API_BASE: string =
  (Constants.expoConfig?.extra?.API_BASE as string) ||
  process.env.EXPO_PUBLIC_API_BASE ||
  "http://192.168.1.10:8000";

const API_KEY: string =
  (Constants.expoConfig?.extra?.API_KEY as string) ||
  process.env.EXPO_PUBLIC_API_KEY ||
  "";

const REQUEST_TIMEOUT_MS = 30000;

function isTokenExpiringSoon(expiresAt?: string): boolean {
  if (!expiresAt) return false;
  const t = new Date(expiresAt).getTime();
  if (!Number.isFinite(t)) return false;
  return t - Date.now() < 24 * 60 * 60 * 1000;
}

async function refreshAccessToken(currentToken: string): Promise<string> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${currentToken}`,
        "X-Request-Id": `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
      },
      signal: controller.signal,
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data?.access_token) {
      throw new Error(data?.detail || "Failed to refresh session");
    }

    await setStoredAccessToken(data.access_token);
    await setStoredTokenMeta({
      tokenType: data.token_type || "bearer",
      expiresAt: data.expires_at || "",
    });

    return data.access_token as string;
  } finally {
    clearTimeout(timer);
  }
}

async function getUsableAccessToken(): Promise<string> {
  const token = await getStoredAccessToken();
  if (!token) return "";

  const meta = await getStoredTokenMeta();
  if (!meta?.expiresAt || !isTokenExpiringSoon(meta.expiresAt)) {
    return token;
  }

  try {
    return await refreshAccessToken(token);
  } catch {
    await clearAllStoredAuth();
    return "";
  }
}

async function buildHeaders(extra?: HeadersInit): Promise<HeadersInit> {
  const accessToken = await getUsableAccessToken();

  const base: Record<string, string> = {
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    "X-Request-Id": `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
  };

  if (!extra) return base;

  if (extra instanceof Headers) {
    const out = new Headers(extra);
    Object.entries(base).forEach(([k, v]) => out.set(k, v));
    return out;
  }

  if (Array.isArray(extra)) {
    return [...extra, ...Object.entries(base)];
  }

  return { ...extra, ...base };
}

async function parseResponse<T>(res: Response): Promise<T> {
  const contentType = res.headers.get("content-type") || "";
  let data: any = {};

  if (contentType.includes("application/json")) {
    data = await res.json().catch(() => ({}));
  } else {
    const text = await res.text().catch(() => "");
    data = text ? { detail: text } : {};
  }

  if (!res.ok) {
    const message =
      data?.detail ||
      data?.message ||
      `Request failed: ${res.status}`;
    throw new Error(message);
  }

  return data as T;
}

async function withTimeout(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
    });
  } catch (err: any) {
    if (err?.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await withTimeout(`${API_BASE}${path}`, {
    headers: await buildHeaders(),
  });
  return parseResponse<T>(res);
}

export async function apiPost<T>(path: string, body?: any): Promise<T> {
  const res = await withTimeout(`${API_BASE}${path}`, {
    method: "POST",
    headers: await buildHeaders({
      "Content-Type": "application/json",
    }),
    body: body ? JSON.stringify(body) : undefined,
  });
  return parseResponse<T>(res);
}

export async function apiPut<T>(path: string, body?: any): Promise<T> {
  const res = await withTimeout(`${API_BASE}${path}`, {
    method: "PUT",
    headers: await buildHeaders({
      "Content-Type": "application/json",
    }),
    body: body ? JSON.stringify(body) : undefined,
  });
  return parseResponse<T>(res);
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  const res = await withTimeout(`${API_BASE}${path}`, {
    method: "POST",
    headers: await buildHeaders(),
    body: form,
  });
  return parseResponse<T>(res);
}

export { API_BASE, API_KEY };