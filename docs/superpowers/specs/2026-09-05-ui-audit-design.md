Last Updated: 2026-09-05

# Design Document: UI/UX Audit Tool

**Date**: 2026-09-05
**Status**: APPROVED
**Context**: `apps/web` is a Next.js 16 + React 19 finance tracker with 6 routes (`/overview`, `/analytics`, `/behavioral`, `/business`, `/logs`, `/reward`). There is no automated UI/UX quality gate today.
**Objective**: A monorepo-resident tool (`tools/ui-audit/`) that runs an end-to-end UI/UX audit on `apps/web`, posts a summary to PRs, diffs against a git-tracked baseline, integrates with GitHub Actions, and uses a test-only auth endpoint to exercise real session state.

## 1. Problem Statement

We have no automated, repeatable UI/UX quality gate. Manual review misses:

1. Regressions in accessibility (a11y) introduced by new components.
2. New console errors / warnings on routes after refactors.
3. Visual or interaction regressions on small viewports.
4. Performance regressions below an agreed threshold.
5. Pages that render blank or break for authenticated users.

Today, "the UI looks fine" is asserted by a human clicking around. We want a tool that:

- Runs the same checks locally and in CI, on every PR.
- Catches critical regressions before merge.
- Posts a clear, actionable summary to the PR.
- Tracks history via git-committed baselines so regressions are attributable to a change.
- Is reliable enough that engineers trust the signal — false positives get it disabled.

## 2. Approach: Monolithic Node script with subcommands

A single Node package at `tools/ui-audit/` with one entry point and a set of focused internal modules. Subcommands keep the CLI surface small; the CI workflow is a thin wrapper that calls the same script a developer would call locally.

### 2.1 Why monolithic-with-modules (not microservices, not split action)

- **One code path, two consumers (local + CI).** Splitting the CI integration into a composite action only pays off if there is a second repo to share with. There is not.
- **All subsystems reachable from one Node process.** No daemon, no HTTP API, no state file outside git.
- **Each subsystem is a focused module** (`lib/auth.mjs`, `lib/baseline.mjs`, `lib/comment.mjs`, …) with a small async surface. Testable in isolation; replaceable in isolation.

### 2.2 Subcommands

- `audit run` — full audit: boot `apps/web`, authenticate, audit each route, run Lighthouse, write report, diff against baseline, optionally post PR comment, exit non-zero on critical findings.
- `audit baseline update` — capture the current audit as the new baseline for the current git ref. No diff, no comment, no fail.
- `audit comment <run-dir>` — post or update a PR comment for a finished audit run. Idempotent (updates the bot's previous comment on the same PR if found).

## 3. Architecture

```
tools/ui-audit/
├── package.json                # @finance-tracker/ui-audit
├── audit.mjs                   # CLI entry; subcommand dispatch
├── lib/
│   ├── server.mjs              # Boots apps/web dev server, waits for ready, teardown
│   ├── auth.mjs                # Calls /api/test-auth/login, sets Playwright cookies
│   ├── routes.mjs              # Hardcoded route list
│   ├── scan.mjs                # Per-route: navigate, screenshot, axe, console capture
│   ├── lighthouse.mjs          # Spawns `lighthouse` CLI per route, parses JSON
│   ├── baseline.mjs            # Read/write baselines/<ref>.json, diff(current, baseline)
│   ├── report.mjs              # Writes report.json + report.html
│   ├── comment.mjs             # Builds markdown summary, posts/updates via gh API
│   ├── grade.mjs               # Computes grade + critical/warn classification
│   ├── retry.mjs               # Retry-with-backoff wrapper for transient ops
│   ├── ci.mjs                  # Detects CI env, resolves PR/base ref, GitHub token
│   └── selfcheck.mjs           # Asserts report.html is well-formed before exit
├── audit.config.example.yml   # Sample config (thresholds, viewport list, …)
├── README.md
└── .gitignore                  # Ignore artifacts/, keep baselines/
```

### 3.1 Data flow (single `audit run`)

1. **`server.mjs`** — Spawns `pnpm --filter @finance-tracker/web dev` via `child_process.spawn`. Polls `http://localhost:3000` with `wait-on` (60s timeout). On exit or signal, SIGKILL the process tree (no orphan `next` on Windows).
2. **`auth.mjs`** — POSTs `{email, password}` to `http://localhost:3000/api/test-auth/login` (form fields from `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` env, read with `fs` — no shell). Stores the returned session cookie in the Playwright browser context.
3. **`scan.mjs`** — For each route × each viewport (`1440x900`, `768x1024`, `375x812`): navigate, wait for `networkidle` + `document.readyState === 'complete'` + 1500ms settle (framer-motion), set `reducedMotion: 'reduce'`, screenshot, run `@axe-core/playwright`, capture `console` and `pageerror` events, check every `<img>` for naturalWidth > 0 and every `<a href>` for a 2xx on `fetch(href, {method: 'HEAD'})`. Per-route wrap in `Promise.race` with 45s timeout.
4. **`lighthouse.mjs`** — For each route (desktop preset only): spawn `npx --no-install lighthouse <url> --preset=desktop --output=json --output-path=<tmp> --chrome-flags='--headless=new --no-sandbox' --quiet`. Parse the four scores (performance, a11y, best-practices, SEO).
5. **`baseline.mjs`** — `git rev-parse HEAD` for current ref; resolve the comparison ref as `GITHUB_BASE_REF` (set in CI) or `main` (local default). Read `tools/ui-audit/baselines/<comparison-ref>.json` if present, else `tools/ui-audit/baselines/main.json`. Compute per-metric delta.
6. **`grade.mjs`** — Apply failure policy (see §5). Returns `{ grade, critical, warn }`.
7. **`report.mjs`** — Writes `artifacts/<run-id>/report.json` (full structured data) and `report.html` (single static file, no JS framework; embeds base64 screenshots if small, file paths if large).
8. **`ci.mjs` + `comment.mjs`** — If `GITHUB_TOKEN` and PR context are present, post/update a comment. Otherwise no-op.
9. **`selfcheck.mjs`** — Reads the written `report.html`, asserts it contains the string `"UI/UX Audit Report"` and parses as HTML. Catches "script ran but produced garbage."
10. Exit. Code 0 on success or warn-only; 1 on critical findings.

### 3.2 Per-module contracts (interfaces)

Each module exports an async function. Inputs are plain objects; outputs are plain objects. No module imports from another module's internals.

- `server.boot({ port }) -> { url, stop() }`
- `auth.login({ baseUrl, email, password }) -> { cookieHeader }`
- `scan.run({ browser, url, route, viewports }) -> { route, findings: [...] }`
- `lighthouse.run({ url, outDir }) -> { performance, accessibility, bestPractices, seo }`
- `baseline.read({ ref }) -> Baseline | null`
- `baseline.diff({ current, baseline }) -> { deltas: [...] }`
- `report.write({ runId, data, outDir }) -> { jsonPath, htmlPath }`
- `comment.postOrUpdate({ token, owner, repo, pr, body }) -> { id, action }`
- `grade.compute({ findings, deltas, lighthouse }) -> { grade, critical, warn }`
- `retry.withBackoff({ fn, attempts, baseMs }) -> T`
- `ci.detect() -> { isCI, owner, repo, pr, sha, baseSha } | null`

## 4. The Test-Only Auth Endpoint

A new Next.js route at `apps/web/src/app/api/test-auth/login/route.ts`. Behavior:

- **Only mounted when `process.env.NODE_ENV !== 'production'`.** The route file itself short-circuits with a 404 in production builds; this is enforced in the handler, not just in CI config.
- Accepts `POST { email, password }`. If both match a test user, sets a session cookie (same cookie the real auth flow sets — reuses whatever the real login route already sets, no parallel auth code).
- Test user credentials come from `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` env vars. The handler returns 404 if those env vars are not set, so production never has a default.
- No rate limiting, no fancy validation — by design. This endpoint is a test seam, not a feature.

**Why a real endpoint, not cookie injection:** the audit must catch regressions in the auth-dependent parts of the UI (server components that gate on session, client-side redirects on unauthenticated access, etc.). Cookie injection would skip those.

**Why not drive the real login form:** flaky (CSS selector drift), slow, and useless when the real form is the thing being audited.

## 5. Failure Policy (what blocks a PR)

Strict by default. Thresholds are checked by `grade.mjs`. Any one of the following → exit 1 → CI check fails:

| Category | Critical (fail) | Warn (report only) |
|---|---|---|
| a11y (axe) | Any `critical` or `serious` impact violation | `moderate` or `minor` |
| Console | Any `error` event | `warning` events |
| Page errors | Any uncaught `pageerror` | — |
| Broken assets | Any `<img>` with `naturalWidth === 0` or 4xx/5xx on link HEAD | — |
| Lighthouse perf | Score < 50, OR regression > 10 points vs baseline | Score 50–69, regression 5–10 points |
| Lighthouse a11y | Score < 90 | 90–94 |
| Grade | F or D (driven by count of above) | C |
| Auth | Login endpoint returns non-2xx or no cookie set | — |
| Report integrity | `selfcheck.mjs` fails on the generated HTML | — |

Thresholds live in `audit.config.example.yml` and are copied to `audit.config.yml` per-repo. The default file is the table above; users can override.

## 6. Baselines

- **Format:** JSON, one file per ref: `tools/ui-audit/baselines/main.json`, `tools/ui-audit/baselines/<sha>.json`, etc.
- **Versioned in git.** The `.gitignore` excludes `artifacts/` and `node_modules/` but **not** `baselines/`.
- **Update flow:** `pnpm audit:ui:baseline` runs `audit baseline update`. The committed JSON contains per-route: axe violation counts by impact, console error count, Lighthouse scores, grade. **No screenshots in baselines** (would bloat the repo; visual diff is out of scope).
- **PR diff:** `baseline.mjs` resolves the PR's base SHA via `GITHUB_BASE_REF` + `git rev-parse origin/<base>`. Falls back to `main` if unset.
- **First run on a route** = no baseline; the run produces a baseline-class report but the diff section reads "no baseline yet."

## 7. PR Comment

Posted by `comment.mjs` using the `GITHUB_TOKEN` (provided by Actions) via the REST API `POST /repos/{owner}/{repo}/issues/{pr}/comments`. Idempotency: the comment body contains a stable marker (`<!-- ui-audit:run:<run-id> -->`); before posting, the script `GET`s existing comments, finds one with the same marker for the same `run-id`, and PATCHes it instead.

**Body shape (markdown table + link):**

```markdown
<!-- ui-audit:run:2026-09-05T14-22-03 -->

## UI/UX Audit — run `2026-09-05T14-22-03`

**Grade: B** · 2 critical findings · 4 warnings

| Route | Grade | A11y (axe) | Console | Perf (LH) | Δ vs base |
|---|---|---|---|---|---|
| `/overview` | A | 0 | 0 | 98 | +1 |
| `/analytics` | B | 1 serious | 0 | 87 | -3 |
| `/behavioral` | A | 0 | 0 | 95 | 0 |
| `/business` | C | 0 | 2 errors | 72 | **-15** |
| `/logs` | A | 0 | 0 | 99 | 0 |
| `/reward` | A | 0 | 0 | 96 | +2 |

🔍 [Full HTML report](https://github.com/.../actions/runs/...) · 📄 `artifacts/2026-09-05T14-22-03/report.html`

<sub>Run by `@ui-audit-bot` · baseline: `main@abc1234`</sub>
```

Critical findings also get a short `### Critical findings` section listing them inline so the PR author sees them without clicking through.

## 8. GitHub Actions Integration

Workflow at `.github/workflows/ui-audit.yml`:

- **Triggers:** `pull_request` opened/synchronize/reopened when files match `apps/web/**`, `tools/ui-audit/**`, or `audit.config.yml`.
- **Job:** `ui-audit`, runs on `ubuntu-latest`. Steps:
  1. `actions/checkout@v4` with `fetch-depth: 0` (need base SHA history).
  2. `actions/setup-node@v4` with `pnpm` cache.
  3. `pnpm install --frozen-lockfile`.
  4. `pnpm --filter @finance-tracker/ui-audit exec playwright install --with-deps chromium`.
  5. `npx --no-install lighthouse --version` smoke check (catches missing CLI before the run).
  6. `pnpm audit:ui` with `GITHUB_TOKEN`, `TEST_USER_EMAIL`, `TEST_USER_PASSWORD` from repo secrets.
  7. `actions/upload-artifact@v4` for the whole `tools/ui-audit/artifacts/<run-id>/` directory.
- **Permissions:** `contents: read`, `pull-requests: write`, `id-token: none`.
- **Concurrency:** `group: ui-audit-${{ github.event.pull_request.number }}`, `cancel-in-progress: true` — only the latest run for a PR matters.

## 9. Local Development

- `pnpm install` at repo root pulls the new tool.
- `pnpm audit:ui` — runs the full audit against a local dev server.
- `pnpm audit:ui:baseline` — captures the current state as the new baseline for the current branch.
- `pnpm audit:ui:comment <run-id>` — re-posts a comment for a local run (requires `GITHUB_TOKEN` + `gh` env).
- One self-test: a `tools/ui-audit/tests/smoke.mjs` that asserts the audit script's own `report.html` validates.

## 10. Reliability (the "reliable" in the original ask)

Each fragility point is handled in exactly one place:

| Risk | Mitigation | Module |
|---|---|---|
| Dev server slow to boot | `wait-on` 60s, retried after `next dev` ready event | `server.mjs` |
| Orphan `next` process on failure | SIGKILL process tree on `exit`/`SIGINT`/`uncaughtException` | `server.mjs` |
| Framer-motion not settled | `page.waitForFunction` + 1500ms settle + `reducedMotion: 'reduce'` | `scan.mjs` |
| Route hangs forever | `Promise.race` with 45s per-route timeout | `scan.mjs` |
| axe fails on one route | `try/catch` per route, recorded as `error` finding | `scan.mjs` |
| Lighthouse CLI missing | Smoke-check `--version` before run | `ci.mjs` |
| Lighthouse run fails | `retry.withBackoff` (2 attempts, 1s base) | `retry.mjs` |
| Auth endpoint down | `retry.withBackoff` (3 attempts, 500ms base) on login | `retry.mjs`, `auth.mjs` |
| First run, no baseline | Skip diff, render "no baseline" cell | `baseline.mjs` |
| Comment already posted | Find marker, PATCH instead of POST | `comment.mjs` |
| JSON files with BOM (Windows gotcha) | All writes use `fs.writeFile` with explicit `utf8` encoding; reader strips BOM if present | `report.mjs`, `baseline.mjs` |
| `.env` written via PowerShell | Tool reads env via `process.env`, never writes `.env` | n/a |
| Report script crashes silently | `selfcheck.mjs` validates the HTML it just wrote | `selfcheck.mjs` |
| Port 3000 in use | Server start detects `EADDRINUSE` and exits with a clear message | `server.mjs` |
| Cross-platform (Windows + Linux CI) | No `&&` chaining, no shell-specific commands, `child_process.spawn` with explicit args | all |

## 11. Files Added / Changed

**New files:**
- `tools/ui-audit/package.json`
- `tools/ui-audit/audit.mjs`
- `tools/ui-audit/lib/*.mjs` (11 modules per §3)
- `tools/ui-audit/audit.config.example.yml`
- `tools/ui-audit/README.md`
- `tools/ui-audit/.gitignore`
- `tools/ui-audit/tests/smoke.mjs`
- `tools/ui-audit/baselines/.gitkeep`
- `apps/web/src/app/api/test-auth/login/route.ts` (Next.js test-only auth endpoint)
- `.github/workflows/ui-audit.yml`

**Modified files:**
- `pnpm-workspace.yaml` — add `tools/*` to the `packages` list (1 line).
- Root `package.json` — add scripts: `audit:ui`, `audit:ui:baseline`, `audit:ui:comment` (3 lines).
- Root `.gitignore` — nothing (baselines are tracked; artifacts are gitignored inside the tool's own `.gitignore`).

**Total surface:** ~13 new files, 2 files touched with 1-line and 3-line edits. No changes to existing `apps/web` source beyond the one new route.

## 12. Success Criteria

1. `pnpm install` at repo root succeeds with the new workspace entry.
2. `pnpm audit:ui` against a clean `apps/web` produces a valid `report.html` and exits 0.
3. Introducing a deliberate a11y violation (e.g., missing `alt` on `<img>`) causes the next run to exit 1, the report to mark it critical, and (in CI) a PR comment to appear with the violation listed.
4. First run on a new branch produces a `report.html` with "no baseline yet" in the diff cell, exits 0 if no critical findings.
5. `pnpm audit:ui:baseline` creates `baselines/<sha>.json` with the expected shape; subsequent runs diff against it.
6. GitHub Actions workflow runs end-to-end on a test PR, posts the summary comment, uploads the artifact, and fails the check on critical findings.
7. Smoke test (`tools/ui-audit/tests/smoke.mjs`) passes.

## 13. Risk Assessment

- **Medium: Lighthouse CLI install / Chrome deps in CI.** Lighthouse needs a working Chrome. Mitigated by `playwright install --with-deps chromium` (which gives us a known-good Chrome) and using `--chrome-flags='--headless=new --no-sandbox'`. If the Lighthouse CLI's auto-Chrome-discovery fights Playwright's, we ship a small launcher script.
- **Medium: Baseline bloat in git.** Each baseline JSON is small (a few KB) but they accumulate per ref. Mitigated by storing only `main` + the PR's base SHA, not every commit. A `git gc` policy is out of scope; we accept the growth.
- **Low: Test-only auth endpoint accidentally reachable in prod.** Mitigated by the `NODE_ENV !== 'production'` check inside the handler itself (defense in depth), plus the endpoint returns 404 if `TEST_USER_*` env vars are unset.
- **Low: PR comment noise on every push.** Mitigated by `concurrency.cancel-in-progress` and the idempotent update (one comment per PR, not one per push).
- **Low: AGENTS.md Windows gotchas (BOM, no PowerShell file writes).** Mitigated by using `fs.writeFile` with `utf8` encoding everywhere; no shell invocation of `Set-Content`, `echo`, or `Out-File`.

## 14. Out of Scope (YAGNI)

- Visual regression diffing (pixel-level screenshot diffs). The user explicitly listed visual screenshot capture but not pixel diff. We capture screenshots; comparing them is a future feature.
- Auth via real OAuth providers. The test endpoint covers the seam we need.
- Slack / Discord notifications.
- Trend dashboards over many runs.
- Multi-app auditing (the tool audits `apps/web` only).
- Configurable route discovery from the filesystem. Routes are hardcoded; adding a route is a 1-line PR.
