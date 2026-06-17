import { test, expect, request as apiRequest } from "@playwright/test";
import { randomUser, register } from "./helpers/auth";

const API_URL = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000";

/**
 * End-to-end test of the Kanban flow: create a project, create a
 * recurring task, move it to done, and verify the spawned occurrence.
 */
test.describe("Kanban + Recurring", () => {
  test("create project → create task → move to done → spawn next", async () => {
    const api = await apiRequest.newContext({ baseURL: API_URL });
    try {
      const user = randomUser("kanban");
      const { accessToken } = await register(api, user);
      const authed = await apiRequest.newContext({
        baseURL: API_URL,
        extraHTTPHeaders: { Authorization: `Bearer ${accessToken}` },
      });

      // Create a project (deadline 30 days from now)
      const deadline = new Date(Date.now() + 30 * 86400_000).toISOString();
      const projectRes = await authed.post("/api/projects", {
        data: { title: "E2E test project", deadline },
      });
      expect(projectRes.status()).toBe(201);
      const project = await projectRes.json();

      // Create a recurring weekly task
      const taskRes = await authed.post(
        `/api/projects/${project.id}/tasks`,
        {
          data: {
            title: "Weekly standup",
            story_points: 1,
            recurrence: "weekly",
            deadline: new Date(Date.now() + 7 * 86400_000).toISOString(),
          },
        }
      );
      expect(taskRes.status()).toBe(201);
      const task = await taskRes.json();
      expect(task.recurrence).toBe("weekly");

      // Move the task to "done"
      const moveRes = await authed.post(
        `/api/tasks/${task.id}/move`,
        { data: { status: "done" } }
      );
      expect(moveRes.status()).toBe(200);

      // List tasks for the project — there should be a spawned one
      // with parent_task_id = task.id
      const list = await authed.get(`/api/projects/${project.id}/tasks`);
      expect(list.status()).toBe(200);
      const tasks = await list.json();
      const spawned = tasks.find((t: any) => t.parent_task_id === task.id);
      expect(spawned).toBeTruthy();
      expect(spawned.status).toBe("todo");
      expect(spawned.recurrence).toBe("weekly");
    } finally {
      await api.dispose();
    }
  });

  test("recalculate CPM returns critical path", async () => {
    const api = await apiRequest.newContext({ baseURL: API_URL });
    try {
      const user = randomUser("cpm");
      const { accessToken } = await register(api, user);
      const authed = await apiRequest.newContext({
        baseURL: API_URL,
        extraHTTPHeaders: { Authorization: `Bearer ${accessToken}` },
      });
      const projectRes = await authed.post("/api/projects", {
        data: {
          title: "CPM test",
          deadline: new Date(Date.now() + 30 * 86400_000).toISOString(),
        },
      });
      const project = await projectRes.json();

      // Two tasks: A (3 days), B (5 days, depends on A)
      const a = await authed.post(`/api/projects/${project.id}/tasks`, {
        data: { title: "A", story_points: 3 },
      });
      const aTask = await a.json();
      const b = await authed.post(`/api/projects/${project.id}/tasks`, {
        data: { title: "B", story_points: 5, depends_on: [aTask.id] },
      });
      expect(b.status()).toBe(201);

      // Recalculate CPM
      const recalc = await authed.post(
        `/api/projects/${project.id}/cpm/recalculate`
      );
      expect(recalc.status()).toBe(200);
      const cpm = await recalc.json();
      expect(cpm.project_duration).toBe(8);
      expect(cpm.critical_path).toContain(aTask.id);
    } finally {
      await api.dispose();
    }
  });
});
