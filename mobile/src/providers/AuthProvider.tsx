/**
 * Auth context for the mobile app.
 *
 * Bootstraps from SecureStore, exposes login/register/logout,
 * and gates the rest of the app on a valid access token.  Also
 * wraps the optional biometric prompt.
 */
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter, useSegments } from "expo-router";
import * as LocalAuthentication from "expo-local-authentication";
import * as SecureStore from "expo-secure-store";

import { API_BASE_URL, api, clearTokens, getStoredUser, persistTokens } from "@/lib/api";


const BIOMETRIC_USER_KEY = "smartpm.biometric.user";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: string;
}

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string) => Promise<void>;
  loginWithBiometric: () => Promise<boolean>;
  enableBiometric: () => Promise<void>;
  biometricEnabled: boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);


export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const segments = useSegments();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [biometricEnabled, setBiometricEnabled] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const stored = await getStoredUser<AuthUser>();
        if (stored) setUser(stored);
        setBiometricEnabled(!!(await SecureStore.getItemAsync(BIOMETRIC_USER_KEY)));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Redirect unauthenticated users to /login
  useEffect(() => {
    if (loading) return;
    const inAuthGroup = segments[0] === "(auth)";
    if (!user && !inAuthGroup) {
      router.replace("/login");
    } else if (user && inAuthGroup) {
      router.replace("/(tabs)/projects");
    }
  }, [user, loading, segments, router]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post<{ access_token: string; refresh_token: string; user: AuthUser }>(
      "/api/auth/login",
      { email, password }
    );
    await persistTokens(res.data.access_token, res.data.refresh_token, res.data.user);
    setUser(res.data.user);
  }, []);

  const register = useCallback(async (email: string, name: string, password: string) => {
    const res = await api.post<{ access_token: string; refresh_token: string; user: AuthUser }>(
      "/api/auth/register",
      { email, name, password }
    );
    await persistTokens(res.data.access_token, res.data.refresh_token, res.data.user);
    setUser(res.data.user);
  }, []);

  const logout = useCallback(async () => {
    await clearTokens();
    await SecureStore.deleteItemAsync(BIOMETRIC_USER_KEY);
    setBiometricEnabled(false);
    setUser(null);
  }, []);

  const enableBiometric = useCallback(async () => {
    if (!user) return;
    await SecureStore.setItemAsync(BIOMETRIC_USER_KEY, JSON.stringify(user));
    setBiometricEnabled(true);
  }, [user]);

  const loginWithBiometric = useCallback(async () => {
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: "Đăng nhập vào Smart PM",
      cancelLabel: "Dùng mật khẩu",
    });
    if (!result.success) return false;
    const raw = await SecureStore.getItemAsync(BIOMETRIC_USER_KEY);
    if (!raw) return false;
    // Refresh the token (the old one may have expired)
    try {
      const refresh = await SecureStore.getItemAsync("smartpm.refresh");
      if (!refresh) return false;
      const res = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) return false;
      const json = await res.json();
      await persistTokens(json.access_token, refresh, JSON.parse(raw));
      setUser(JSON.parse(raw));
      return true;
    } catch {
      return false;
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, loading, login, register, loginWithBiometric, enableBiometric, biometricEnabled, logout }),
    [user, loading, login, register, loginWithBiometric, enableBiometric, biometricEnabled, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
