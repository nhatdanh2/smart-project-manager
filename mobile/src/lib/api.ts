/**
 * Mobile HTTP client.
 *
 * Reads the access/refresh tokens from SecureStore and attaches the
 * Bearer header automatically.  When a 401 comes back we attempt
 * one refresh round-trip; if that fails we drop to the login screen.
 */
import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from "axios";
import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";

const API_BASE_URL =
  (Constants.expoConfig?.extra?.apiBaseUrl as string) || "http://localhost:8000";

const ACCESS_KEY = "smartpm.access";
const REFRESH_KEY = "smartpm.refresh";
const USER_KEY = "smartpm.user";

let memoryAccess: string | null = null;
let memoryRefresh: string | null = null;

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
});

api.interceptors.request.use(async (cfg: InternalAxiosRequestConfig) => {
  if (!memoryAccess) {
    memoryAccess = await SecureStore.getItemAsync(ACCESS_KEY);
  }
  if (memoryAccess) {
    cfg.headers.Authorization = `Bearer ${memoryAccess}`;
  }
  return cfg;
});

let refreshing: Promise<string | null> | null = null;
async function tryRefresh(): Promise<string | null> {
  if (refreshing) return refreshing;
  refreshing = (async () => {
    if (!memoryRefresh) {
      memoryRefresh = await SecureStore.getItemAsync(REFRESH_KEY);
    }
    if (!memoryRefresh) return null;
    try {
      const res = await axios.post<{ access_token: string }>(
        `${API_BASE_URL}/api/auth/refresh`,
        { refresh_token: memoryRefresh }
      );
      const newAccess = res.data.access_token;
      await setAccessToken(newAccess);
      return newAccess;
    } catch {
      return null;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

api.interceptors.response.use(
  (r) => r,
  async (err: AxiosError) => {
    const original = err.config as InternalAxiosRequestConfig & { _retried?: boolean };
    if (err.response?.status === 401 && !original._retried) {
      original._retried = true;
      const newAccess = await tryRefresh();
      if (newAccess) {
        original.headers = original.headers ?? {};
        (original.headers as any).Authorization = `Bearer ${newAccess}`;
        return api.request(original);
      }
      await clearTokens();
    }
    return Promise.reject(err);
  }
);

export async function setAccessToken(t: string) {
  memoryAccess = t;
  await SecureStore.setItemAsync(ACCESS_KEY, t);
}
export async function setRefreshToken(t: string) {
  memoryRefresh = t;
  await SecureStore.setItemAsync(REFRESH_KEY, t);
}
export async function setStoredUser(u: object) {
  await SecureStore.setItemAsync(USER_KEY, JSON.stringify(u));
}
export async function getStoredUser<T>(): Promise<T | null> {
  const raw = await SecureStore.getItemAsync(USER_KEY);
  return raw ? (JSON.parse(raw) as T) : null;
}
export async function clearTokens() {
  memoryAccess = null;
  memoryRefresh = null;
  await SecureStore.deleteItemAsync(ACCESS_KEY);
  await SecureStore.deleteItemAsync(REFRESH_KEY);
  await SecureStore.deleteItemAsync(USER_KEY);
}

export async function persistTokens(access: string, refresh: string, user?: object) {
  await setAccessToken(access);
  await setRefreshToken(refresh);
  if (user) await setStoredUser(user);
}

export { API_BASE_URL };
