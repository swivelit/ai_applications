import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";

const PROFILE_KEY = "user_profile_v2";
const ACCESS_TOKEN_KEY = "auth_access_token_v1";
const TOKEN_META_KEY = "auth_token_meta_v1";

export type AuthTokenMeta = {
  tokenType?: string;
  expiresAt?: string;
};

export async function getStoredProfile<T = any>(): Promise<T | null> {
  try {
    const raw = await AsyncStorage.getItem(PROFILE_KEY);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export async function setStoredProfile(value: any): Promise<void> {
  await AsyncStorage.setItem(PROFILE_KEY, JSON.stringify(value));
}

export async function clearStoredProfile(): Promise<void> {
  await AsyncStorage.removeItem(PROFILE_KEY);
}

export async function getStoredAccessToken(): Promise<string> {
  try {
    return (await SecureStore.getItemAsync(ACCESS_TOKEN_KEY)) || "";
  } catch {
    return "";
  }
}

export async function setStoredAccessToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, token, {
    keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
  });
}

export async function clearStoredAccessToken(): Promise<void> {
  await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
}

export async function getStoredTokenMeta(): Promise<AuthTokenMeta | null> {
  try {
    const raw = await SecureStore.getItemAsync(TOKEN_META_KEY);
    return raw ? (JSON.parse(raw) as AuthTokenMeta) : null;
  } catch {
    return null;
  }
}

export async function setStoredTokenMeta(meta: AuthTokenMeta): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_META_KEY, JSON.stringify(meta), {
    keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
  });
}

export async function clearStoredTokenMeta(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_META_KEY);
}

export async function clearAllStoredAuth(): Promise<void> {
  await Promise.all([
    clearStoredAccessToken(),
    clearStoredTokenMeta(),
  ]);
}