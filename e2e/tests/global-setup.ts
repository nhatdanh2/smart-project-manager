import { request } from "@playwright/test";

/**
 * One-shot setup: verify the API is reachable before any tests run.
 * Fails fast with a clear message if ``docker compose up`` never came up.
 */
export default async function globalSetup() {
  const apiURL =
    process.env.PLAYWRIGHT_API_URL || "http://localhost:8000";
  const ctx = await request.newContext({ baseURL: apiURL });
  try {
    const res = await ctx.get("/health", { timeout: 10_000 });
    if (!res.ok()) {
      throw new Error(`API health check returned ${res.status()}`);
    }
  } catch (err) {
    throw new Error(
      `Could not reach the API at ${apiURL}/health. ` +
        `Did you run \`docker compose up\`? (${(err as Error).message})`
    );
  } finally {
    await ctx.dispose();
  }
}
