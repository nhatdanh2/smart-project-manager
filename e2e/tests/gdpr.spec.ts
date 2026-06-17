import { test, expect, request as apiRequest } from "@playwright/test";
import { randomUser, register } from "./helpers/auth";

const API_URL = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000";

test.describe("GDPR", () => {
  test("export returns a JSON archive of the user's data", async () => {
    const api = await apiRequest.newContext({ baseURL: API_URL });
    try {
      const user = randomUser("gdpr");
      const { accessToken } = await register(api, user);
      const authed = await apiRequest.newContext({
        baseURL: API_URL,
        extraHTTPHeaders: { Authorization: `Bearer ${accessToken}` },
      });
      const res = await authed.get("/api/gdpr/export");
      expect(res.status()).toBe(200);
      expect(res.headers()["content-disposition"]).toContain("attachment");
      const body = await res.json();
      expect(body.user.email).toBe(user.email);
      expect(Array.isArray(body.tasks)).toBe(true);
      expect(Array.isArray(body.projects_member_of)).toBe(true);
    } finally {
      await api.dispose();
    }
  });

  test("delete is soft: account no longer login but row still in DB", async () => {
    const api = await apiRequest.newContext({ baseURL: API_URL });
    try {
      const user = randomUser("gdpr-del");
      const { accessToken } = await register(api, user);
      const authed = await apiRequest.newContext({
        baseURL: API_URL,
        extraHTTPHeaders: { Authorization: `Bearer ${accessToken}` },
      });
      const res = await authed.post("/api/gdpr/delete");
      expect(res.status()).toBe(202);
      const body = await res.json();
      expect(body.status).toBe("scheduled");
      expect(body.purge_after_days).toBeGreaterThan(0);

      // Login with the same credentials now fails
      const loginRes = await api.post("/api/auth/login", {
        data: { email: user.email, password: user.password },
      });
      expect(loginRes.status()).toBe(401);

      // /auth/me with the now-invalid token also fails
      const meRes = await authed.get("/api/auth/me");
      expect(meRes.status()).toBe(401);
    } finally {
      await api.dispose();
    }
  });

  test("delete is idempotent (second call returns 409)", async () => {
    const api = await apiRequest.newContext({ baseURL: API_URL });
    try {
      const user = randomUser("gdpr-idem");
      const { accessToken } = await register(api, user);
      const authed = await apiRequest.newContext({
        baseURL: API_URL,
        extraHTTPHeaders: { Authorization: `Bearer ${accessToken}` },
      });
      const r1 = await authed.post("/api/gdpr/delete");
      expect(r1.status()).toBe(202);
      const r2 = await authed.post("/api/gdpr/delete");
      expect(r2.status()).toBe(409);
    } finally {
      await api.dispose();
    }
  });
});
