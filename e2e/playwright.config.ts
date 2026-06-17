import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for the Smart PM end-to-end tests.
 *
 * Usage:
 *   # Default: spin up the stack with `docker compose` (see webServer)
 *   npx playwright test
 *
 *   # Against an already-running stack (CI on staging)
 *   PLAYWRIGHT_BASE_URL=https://staging.spm.example.com \
 *     npx playwright test
 *
 *   # Run a single test in headed mode
 *   npx playwright test --headed --grep "login"
 */
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const API_URL = process.env.PLAYWRIGHT_API_URL || "http://localhost:8000";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",

  timeout: 30_000,
  expect: { timeout: 5_000 },

  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 10_000,
  },

  // Auto-start the local dev stack unless we're pointed at a remote
  // (e.g. staging).  ``webServer`` waits for the URL to return 2xx.
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: "cd .. && docker compose up --wait",
        url: BASE_URL,
        timeout: 120_000,
        reuseExistingServer: !process.env.CI,
        stdout: "pipe",
        stderr: "pipe",
      },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
  ],

  // Quick health check that the API is up.
  globalSetup: require.resolve("./tests/global-setup.ts"),

  metadata: {
    baseURL: BASE_URL,
    apiURL: API_URL,
  },
});
