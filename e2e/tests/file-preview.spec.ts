import { test, expect, request as apiRequest } from "@playwright/test";
import { randomUser, register } from "./helpers/auth";
import { readFileSync } from "fs";
import { resolve } from "path";

const API_URL = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000";

/**
 * Uploads a tiny PDF to a project and verifies the file preview
 * endpoints (meta + streaming) work end-to-end.
 */
test.describe("File preview", () => {
  test("upload PDF → meta returns kind=pdf → preview streams bytes", async () => {
    const api = await apiRequest.newContext({ baseURL: API_URL });
    try {
      const user = randomUser("files");
      const { accessToken } = await register(api, user);
      const authed = await apiRequest.newContext({
        baseURL: API_URL,
        extraHTTPHeaders: { Authorization: `Bearer ${accessToken}` },
      });

      // Create a project first (file upload needs one)
      const projectRes = await authed.post("/api/projects", {
        data: {
          title: "File preview E2E",
          deadline: new Date(Date.now() + 86400_000).toISOString(),
        },
      });
      const project = await projectRes.json();

      // 1×1 transparent PNG (43 bytes).  Use the bytes inline so the
      // test doesn't depend on fixture files.
      const pngBytes = Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
        "base64"
      );

      const upload = await authed.post(
        `/api/projects/${project.id}/meetings`,
        {
          multipart: {
            title: "tiny.png",
            file: {
              name: "tiny.png",
              mimeType: "image/png",
              buffer: pngBytes,
            },
          },
        }
      );
      expect(upload.status()).toBe(201);
      const meeting = await upload.json();
      expect(meeting.file_url).toBeTruthy();

      // Meta endpoint
      const meta = await authed.get(
        `/api/files/meetings/${meeting.id}/meta`
      );
      expect(meta.status()).toBe(200);
      const metaJson = await meta.json();
      expect(metaJson.kind).toBe("image");
      expect(metaJson.mime).toBe("image/png");
      expect(metaJson.size).toBe(pngBytes.length);

      // Preview endpoint returns 200 + same byte length
      const preview = await authed.get(
        `/api/files/meetings/${meeting.id}/preview`
      );
      expect(preview.status()).toBe(200);
      const previewBytes = await preview.body();
      expect(previewBytes.length).toBe(pngBytes.length);

      // Range request (bytes 0-9) returns 206 with 10 bytes
      const rangeRes = await authed.get(
        `/api/files/meetings/${meeting.id}/preview`,
        { headers: { Range: "bytes=0-9" } }
      );
      expect(rangeRes.status()).toBe(206);
      const rangeBody = await rangeRes.body();
      expect(rangeBody.length).toBe(10);
    } finally {
      await api.dispose();
    }
  });

  test("preview without membership returns 403", async () => {
    const api = await apiRequest.newContext({ baseURL: API_URL });
    try {
      // Alice creates a project + meeting
      const alice = randomUser("alice");
      const { accessToken: aliceToken } = await register(api, alice);
      const aliceCtx = await apiRequest.newContext({
        baseURL: API_URL,
        extraHTTPHeaders: { Authorization: `Bearer ${aliceToken}` },
      });
      const project = await (
        await aliceCtx.post("/api/projects", {
          data: { title: "private", deadline: new Date(Date.now() + 86400_000).toISOString() },
        })
      ).json();
      const meeting = await (
        await aliceCtx.post(`/api/projects/${project.id}/meetings`, {
          multipart: {
            title: "x.txt",
            file: {
              name: "x.txt",
              mimeType: "text/plain",
              buffer: Buffer.from("hello"),
            },
          },
        })
      ).json();

      // Bob is not a member
      const bob = randomUser("bob");
      const { accessToken: bobToken } = await register(api, bob);
      const bobCtx = await apiRequest.newContext({
        baseURL: API_URL,
        extraHTTPHeaders: { Authorization: `Bearer ${bobToken}` },
      });
      const res = await bobCtx.get(
        `/api/files/meetings/${meeting.id}/meta`
      );
      expect(res.status()).toBe(403);
    } finally {
      await api.dispose();
    }
  });
});
