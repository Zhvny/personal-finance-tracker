import { expect, test } from "@playwright/test";

const apiURL = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8444";

test("homepage serves with app title", async ({ page }) => {
  const resp = await page.goto("/");
  expect(resp?.ok()).toBeTruthy();
  // page metadata title is 'Dashboard' (layout template appends site name
  // when present — match the stable page part either way).
  await expect(page).toHaveTitle(/Dashboard/);
});

test("gateway /health reports ok (smoke gate blocks degraded/unhealthy)", async ({ request }) => {
  const res = await request.get(`${apiURL}/health`);
  // Strict: degraded/unhealthy must fail the gate — partial outages
  // should surface, not pass silently.
  // NOTE (deferred): Playwright `webServer` is not configured in this repo,
  // so E2E assumes gateway+web already running. Infra change out of scope.
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { status?: unknown };
  expect(body.status).toBe("ok");
});
