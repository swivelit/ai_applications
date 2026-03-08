import AsyncStorage from "@react-native-async-storage/async-storage";
import { apiGet, apiPost, apiPut } from "./api";

const KEY = "user_profile_v2";

export type LocalUserProfile = {
  userId?: string;
  name: string;
  place?: string;
  timezone?: string;
  assistantName?: string;
  accessToken?: string;
  tokenType?: string;
  expiresAt?: string;
};

export type DailyRoutinePayload = {
  workStart?: string;
  workEnd?: string;
  sleep: string;
  wake: string;
  dailyHabits?: string;
};

export async function getProfile(): Promise<LocalUserProfile | null> {
  const raw = await AsyncStorage.getItem(KEY);
  return raw ? JSON.parse(raw) : null;
}

export async function saveProfile(profile: LocalUserProfile) {
  await AsyncStorage.setItem(KEY, JSON.stringify(profile));
}

export async function clearProfile() {
  await AsyncStorage.removeItem(KEY);
}

export async function createProfileOnBackend(p: LocalUserProfile) {
  const user = await apiPost<any>("/users", {
    name: p.name,
    place: p.place,
    timezone: p.timezone || "Asia/Kolkata",
    assistant_name: p.assistantName || "Ellie",
  });

  const merged: LocalUserProfile = {
    ...p,
    userId: user.id,
    timezone: user.timezone || p.timezone || "Asia/Kolkata",
    assistantName: user.assistant_name || p.assistantName || "Ellie",
    accessToken: user.access_token || "",
    tokenType: user.token_type || "bearer",
    expiresAt: user.expires_at || "",
  };

  await saveProfile(merged);
  return merged;
}

export async function submitQuestionnaire(userId: string, payload: DailyRoutinePayload) {
  return apiPost(`/users/${encodeURIComponent(userId)}/questionnaire`, { payload });
}

export async function saveDailyRoutine(userId: string, payload: DailyRoutinePayload) {
  return apiPut(`/users/${encodeURIComponent(userId)}/daily-routine`, {
    wake_time: payload.wake,
    sleep_time: payload.sleep,
    work_start: payload.workStart || null,
    work_end: payload.workEnd || null,
    daily_habits: payload.dailyHabits || "",
  });
}

export async function generateDailyCheckins(userId: string) {
  return apiPost<{ checkins: { title: string; when: string; message: string }[] }>(
    `/users/${encodeURIComponent(userId)}/generate-daily-checkins`,
    {}
  );
}

export async function getBackendProfile(userId: string) {
  return apiGet(`/api/profile/${encodeURIComponent(userId)}`);
}

export async function getPersonality(userId: string) {
  return apiGet(`/users/${encodeURIComponent(userId)}/personality`);
}

export async function savePersonality(userId: string, answers: Record<string, any>) {
  return apiPost(`/users/${encodeURIComponent(userId)}/personality`, { answers });
}