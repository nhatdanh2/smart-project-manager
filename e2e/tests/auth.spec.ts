import { test, expect } from "@playwright/test";
import { randomUser, register, login } from "./helpers/auth";

const API_URL = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000";

test.describe("Auth", () => {
  test("register → login → /auth/me round trip", async ({ request, baseURL }) => {
    const api = await request.newContext({ baseURL: API_URL });
    try {
      const user = randomUser("alice");
      const reg = await register(api, user);
      expect(reg.accessToken).toBeTruthy();
      expect(reg.userId).toBeTruthy();

      // /auth/me via the page context using the token
      const meRes = await request.get("/api/auth/me", {
        headers: { Authorization: `Bearer ${reg.accessToken}` },
      });
      expect(meRes.status()).toBe(200);
      const me = await meRes.json();
      expect(me.email).toBe(user.email);
      expect(me.name).toBe(user.name);

      // Login with the same credentials returns a new token
      const accessToken = await login(api, user);
      expect(accessToken).toBeTruthy();
    } finally {
      await api.dispose();
    }
  });

  test("login with wrong password returns 401", async ({ request }) => {
    const api = await request.newContext({ baseURL: API_URL });
    try {
      const user = randomUser("bob");
      await register(api, user);
      const res = await api.post("/api/auth/login", {
        data: { email: user.email, password: "wrong-password" },
      });
      expect(res.status()).toBe(401);
    } finally {
      await api.dispose();
    }
  });

  test("/auth/me without token returns 401", async ({ request }) => {
    const res = await request.get("/api/auth/me");
    expect(res.status()).toBe(401);
  });

  test("rate limit kicks in after 10 login attempts/minute", async ({ request }) => {
    // The configured default is 10/minute.  Make 12 attempts fast.
    let saw429 = false;
    for (let i = 0; i < 12; i++) {
      const res = await request.post("/api/auth/login", {
        data: { email: "no-such@example.com", password: "x" },
      });
      if (res.status() === 429) {
        saw429 = true;
        break;
      }
    }
    expect(saw429).toBe(true);
  });
});
