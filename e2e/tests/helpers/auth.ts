import { APIRequestContext, request } from "@playwright/test";

/**
 * Helpers for authenticating against the Smart PM API.  Tests should
 * use ``login`` to obtain a token, then call ``authenticatedContext``
 * to get a request context that auto-attaches the Bearer token.
 */

export interface AuthUser {
  email: string;
  name: string;
  password: string;
}

export function randomUser(prefix = "user"): AuthUser {
  const id = Math.random().toString(36).slice(2, 10);
  return {
    email: `${prefix}-${id}@e2e.test`,
    name: `${prefix} ${id}`,
    password: "TestPassword123!",
  };
}

export async function register(
  api: APIRequestContext,
  user: AuthUser
): Promise<{ accessToken: string; refreshToken: string; userId: string }> {
  const res = await api.post("/api/auth/register", { data: user });
  if (!res.ok()) {
    throw new Error(
      `register failed: ${res.status()} ${await res.text()}`
    );
  }
  const body = await res.json();
  return {
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
    userId: body.user.id,
  };
}

export async function login(
  api: APIRequestContext,
  user: AuthUser
): Promise<string> {
  const res = await api.post("/api/auth/login", { data: user });
  if (!res.ok()) {
    throw new Error(`login failed: ${res.status()} ${await res.text()}`);
  }
  const body = await res.json();
  return body.access_token;
}

export async function authenticatedContext(
  baseURL: string,
  accessToken: string
): Promise<APIRequestContext> {
  const ctx = await request.newContext({
    baseURL,
    extraHTTPHeaders: { Authorization: `Bearer ${accessToken}` },
  });
  return ctx;
}
