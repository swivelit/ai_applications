import Constants from "expo-constants";

export const API_BASE: string =
  (Constants.expoConfig?.extra?.API_BASE as string) ||
  process.env.EXPO_PUBLIC_API_BASE ||
  "http://192.168.1.10:8000";

async function parseResponse<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error((data as any)?.detail || `Request failed: ${res.status}`);
  }
  return data as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  return parseResponse<T>(res);
}

export async function apiPost<T>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  return parseResponse<T>(res);
}

export async function apiPut<T>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  return parseResponse<T>(res);
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: form,
  });
  return parseResponse<T>(res);
}