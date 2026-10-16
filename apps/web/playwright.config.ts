import { defineConfig } from "@playwright/test";

// Smoke E2E: CI provides the stack (docker compose: web on :3000,
// gateway on :8444), so no webServer here — keep this file environment-only.
const webURL = process.env.PLAYWRIGHT_WEB_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: "html",
  use: {
    baseURL: webURL,
  },
  projects: [{ name: "chromium", use: {} }],
});
