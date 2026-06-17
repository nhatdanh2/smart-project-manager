"use client";

import axios, { AxiosError, AxiosInstance } from "axios";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let inMemoryAccessToken: string | null = null;
let inMemoryRefreshToken: string | null = null;

export function setTokens(access: string | null, refresh: string | null) {
  inMemoryAccessToken = access;
  inMemoryRefreshToken = refresh;
  if (typeof window !== "undefined") {
    if (access) localStorage.setItem("spm_access", access);
    else localStorage.removeItem("spm_access");
    if (refresh) localStorage.setItem("spm_refresh", refresh);
    else localStorage.removeItem("spm_refresh");
  }
}

export function getAccessToken(): string | null {
  if (inMemoryAccessToken) return inMemoryAccessToken;
  if (typeof window !== "undefined") {
    inMemoryAccessToken = localStorage.getItem("spm_access");
    return inMemoryAccessToken;
  }
  return null;
}

export function getRefreshToken(): string | null {
  if (inMemoryRefreshToken) return inMemoryRefreshToken;
  if (typeof window !== "undefined") {
    inMemoryRefreshToken = localStorage.getItem("spm_refresh");
    return inMemoryRefreshToken;
  }
  return null;
}

export const api: AxiosInstance = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  if (refreshing) return refreshing;
  const refresh = getRefreshToken();
  if (!refresh) return null;
  refreshing = (async () => {
    try {
      const res = await axios.post(`${API_BASE}/api/auth/refresh`, null, {
        params: { refresh_token: refresh },
      });
      const { access_token, refresh_token } = res.data as {
        access_token: string;
        refresh_token: string;
      };
      setTokens(access_token, refresh_token);
      return access_token;
    } catch (err) {
      setTokens(null, null);
      return null;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    if (error.response?.status === 429) {
      // Surface a friendlier error so the UI can show a toast.
      const detail =
        (error.response.data as { detail?: string })?.detail ||
        "Quá nhiều yêu cầu. Vui lòng thử lại sau ít phút.";
      if (typeof window !== "undefined") {
        // Lazy-load to avoid a circular dep with useAuth
        const { toast } = await import("sonner");
        toast.error(detail);
      }
      return Promise.reject(new Error(detail));
    }
    // 5xx -> forward to Sentry (best effort)
    if (
      error.response?.status &&
      error.response.status >= 500 &&
      typeof window !== "undefined"
    ) {
      try {
        const { captureException } = await import("@/lib/observability");
        captureException(error, {
          url: error.config?.url,
          method: error.config?.method,
          status: error.response.status,
        });
      } catch {
        // noop
      }
    }
    const original = error.config as (typeof error.config & { _retry?: boolean }) | undefined;
    if (
      error.response?.status === 401 &&
      original &&
      !original._retry &&
      getRefreshToken()
    ) {
      original._retry = true;
      const newToken = await tryRefresh();
      if (newToken) {
        original.headers = original.headers || {};
        (original.headers as Record<string, string>).Authorization = `Bearer ${newToken}`;
        return api.request(original);
      }
    }
    return Promise.reject(error);
  }
);

export const API_BASE_URL = API_BASE;
