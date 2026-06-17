import { test, expect, request as apiRequest } from "@playwright/test";
import { randomUser, register } from "./helpers/auth";

const API_URL = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000";

test.describe("Presence", () => {
  test("presence endpoint requires auth", async ({ request }) => {
    const res = await request.get("/api/ws/projects/abc/presence");
    expect([401, 422]).toContain(res.status());
  });

  test("two users joining a project see each other in presence", async () => {
    const api = await apiRequest.newContext({ baseURL: API_URL });
    try {
      const owner = randomUser("owner");
      const guest = randomUser("guest");
      const { accessToken: ownerToken } = await register(api, owner);
      const { accessToken: guestToken } = await register(api, guest);

      const ownerCtx = await apiRequest.newContext({
        baseURL: API_URL,
        extraHTTPHeaders: { Authorization: `Bearer ${ownerToken}` },
      });
      const project = await (
        await ownerCtx.post("/api/projects", {
          data: { title: "presence test", deadline: new Date(Date.now() + 86400_000).toISOString() },
        })
      ).json();
      await ownerCtx.post(`/api/projects/${project.id}/members`, {
        data: { user_id: (await register(api, guest)).userId, role: "member" },
      });

      // Open WebSockets (use the standard WebSocket lib from Node 22+).
      const wsURL = (API_URL.replace(/^http/, "ws")) + `/ws/projects/${project.id}`;
      const ownerWs = new WebSocket(`${wsURL}?token=${ownerToken}`);
      const guestWs = new WebSocket(`${wsURL}?token=${guestToken}`);

      const ownerMessages: any[] = [];
      const guestMessages: any[] = [];
      ownerWs.onmessage = (e) => ownerMessages.push(JSON.parse(e.data));
      guestWs.onmessage = (e) => guestMessages.push(JSON.parse(e.data));

      // Wait for hello + presence on each socket
      await new Promise((res) => setTimeout(res, 1500));

      ownerWs.close();
      guestWs.close();

      // Each side should have received at least one presence event
      // (sent on join + on every heartbeat until close).
      const ownerPresence = ownerMessages.filter((m) => m.type === "presence");
      const guestPresence = guestMessages.filter((m) => m.type === "presence");
      expect(ownerPresence.length).toBeGreaterThan(0);
      expect(guestPresence.length).toBeGreaterThan(0);

      // The latest presence event from the owner should include both
      // users.
      const last = ownerPresence[ownerPresence.length - 1];
      const ids = (last.members as any[]).map((m) => m.userId);
      expect(ids.length).toBeGreaterThanOrEqual(2);
    } finally {
      await api.dispose();
    }
  });
});
