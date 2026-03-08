import Constants from "expo-constants";

const API_BASE: string =
  (Constants.expoConfig?.extra?.API_BASE as string) ||
  process.env.EXPO_PUBLIC_API_BASE ||
  "http://192.168.1.10:8000";

const API_KEY: string =
  (Constants.expoConfig?.extra?.API_KEY as string) ||
  process.env.EXPO_PUBLIC_API_KEY ||
  "";

const REQUEST_TIMEOUT_MS = 30000;

function buildHeaders(extra?: HeadersInit): HeadersInit {
  const base: Record<string, string> = {
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
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
    headers: buildHeaders(),
  });
  return parseResponse<T>(res);
}

export async function apiPost<T>(path: string, body?: any): Promise<T> {
  const res = await withTimeout(`${API_BASE}${path}`, {
    method: "POST",
    headers: buildHeaders({
      "Content-Type": "application/json",
    }),
    body: body ? JSON.stringify(body) : undefined,
  });
  return parseResponse<T>(res);
}

export async function apiPut<T>(path: string, body?: any): Promise<T> {
  const res = await withTimeout(`${API_BASE}${path}`, {
    method: "PUT",
    headers: buildHeaders({
      "Content-Type": "application/json",
    }),
    body: body ? JSON.stringify(body) : undefined,
  });
  return parseResponse<T>(res);
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  const res = await withTimeout(`${API_BASE}${path}`, {
    method: "POST",
    headers: buildHeaders(),
    body: form,
  });
  return parseResponse<T>(res);
}

export { API_BASE, API_KEY };