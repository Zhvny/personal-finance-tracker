# Automated Testing Pipeline — Design Spec

**Date:** 2025-09-16  
**Status:** Approved  
**Scope:** Legacy UI (`packages/web`) + backend API testing inside Docker Compose, gated by CI.

---

## 1. Goal

A reproducible, Docker-native test pipeline that answers one question: **"Can this code be deployed?"**

Three layers: unit → integration → E2E. All runnable locally and in CI. Failure at any layer blocks the deployability gate.

---

## 2. Architecture

### 2.1 Test Compose File

New file: `docker-compose.test.yml`

Extends `docker-compose.yml` with:
- Isolated `postgres-test` service (separate container/volume from dev DB)
- `test-runner` ephemeral container that executes all test commands
- All existing microservices + gateway (reused from base compose)
- `web` service built from `packages/web/Dockerfile`

```
docker-compose.test.yml
├── postgres-test (port 5433, db: finance_tracker_test)
├── gateway (port 8444)
├── platform, ledger, portfolio, market, insights, engagement
├── web (packages/web, port 3000)
└── test-runner (depends_on all above, runs pytest + vitest + playwright)
```

### 2.2 Why a Dedicated Test Runner Container

- Parity: CI and local use identical environment
- No host dependency on Node/Python versions
- Artifacts (screenshots, coverage XML) persist via named volume or bind mount

---

## 3. Test Layers

### 3.1 Layer 1: Unit Tests

**Backend (pytest)**
- Command: `pytest tests/ packages/api/tests/ -m "not integration and not e2e"`
- Database: **SQLite in-memory** via `USE_SQLITE_ONLY=true` (already supported in `tests/conftest.py`)
- Fast, no Docker DB needed
- Current coverage threshold: `fail_under = 40` (from `pyproject.toml`)
- Lint gate: `ruff check .` runs before pytest

**Frontend (Vitest)**
- Command: `pnpm --filter web test:run` (non-watch mode)
- Location: `packages/web/tests/**/*.test.{js,jsx}`
- Coverage: `--coverage` flag, threshold 60% (configurable)
- Existing tests already present; no new unit tests required in this phase

**Execution order:** Lint → Backend unit → Frontend unit. Fail fast on first error.

---

### 3.2 Layer 2: Integration Tests

**Location:** `tests/integration/` (new directory)

**Database:**
- Dedicated `postgres-test` container
- Migrations applied via `python migrations/runner.py apply --database-url $TEST_DATABASE_URL`
- Minimal seed data via pytest fixture (users, sample transactions)

**Scope:**
- Auth flow: API key validation, JWT issuance
- CRUD endpoints: expenses, income, investments
- Multi-schema isolation: verify ledger data doesn't leak to portfolio schema
- Gateway routing: request to `/api/ledger/...` hits ledger service

**Test client:** `httpx.AsyncClient` against `http://gateway:8444` (internal Docker DNS)

**Marker:** `@pytest.mark.integration` — excluded from unit test runs

**Example test structure:**
```
tests/integration/
├── __init__.py
├── conftest.py              # test client fixture, DB setup/teardown
├── test_auth.py
├── test_expenses.py
├── test_multitenant.py
└── test_gateway_routing.py
```

---

### 3.3 Layer 3: End-to-End Tests (Playwright)

**Location:** `packages/web/tests/e2e/` (new directory)

**Target:** `http://web:3000` (internal Docker network; uses `VITE_API_BASE` pointing to gateway)

**Playwright config:** `packages/web/playwright.config.ts`
- `webServer: { url: "http://web:3000", command: "pnpm preview --port 3000", reuseExistingServer: false }`
- Or: rely on `docker-compose.test.yml` bringing up `web` service; Playwright connects to existing server
- Reporter: `line` for CI, `html` for local
- Screenshots: `only-on-failure`
- Trace: `retain-on-failure`

**Test flows:**

1. **Login** (`test_login.spec.ts`)
   - Navigate to `/`
   - Enter API key, submit
   - Assert redirect to `/dashboard`
   - Assert token stored in sessionStorage

2. **Dashboard** (`test_dashboard.spec.ts`)
   - Verify Goals, Health Score, Safe To Spend widgets load

3. **Expense Tracker** (`test_expense_tracker.spec.ts`)
   - Navigate to `/expense-tracker`
   - Assert Recurring + Merchant panels render
   - Add a test expense, verify it appears in list

4. **Investment Tracker** (`test_investment_tracker.spec.ts`)
   - Navigate to `/investment-tracker`
   - Assert NetWorth tab renders
   - Verify holdings table loads

5. **Behavioral Dashboard** (`test_behavioral.spec.ts`)
   - Navigate to `/behavioral`
   - Assert behavioral-finance + insights tabs render

6. **Advanced** (`test_advanced.spec.ts`)
   - Navigate to `/advanced`
   - Assert Goals, Forecast, Budget tabs render

7. **Admin (hidden route)** (`test_admin.spec.ts`)
   - Navigate directly to `/admin`
   - Assert page loads (hidden from sidebar but accessible)
   - Assert logs tab renders

**Base URL handling:** Playwright reads `WEB_BASE_URL` env var (default `http://localhost:3000`). In Docker Compose, this is `http://web:3000`.

---

## 4. CI Pipeline

### 4.1 Workflow File

New file: `.github/workflows/test.yml`

### 4.2 Jobs

```yaml
name: Test & Deployability Gate

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ruff check .

  unit-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: finance_tracker
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: password
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pnpm install
      - run: pip install -r requirements.txt  # or poetry install
      - run: pytest tests/ packages/api/tests/ -m "not integration and not e2e" --ignore=tests/automation
      - run: pnpm --filter web test:run

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: finance_tracker_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: password
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pnpm install
      - run: pip install -r requirements.txt
      - run: python migrations/runner.py apply --database-url ${{ secrets.TEST_DATABASE_URL }}
      - run: pytest tests/integration/ -v

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
      - run: docker compose -f docker-compose.test.yml logs test-runner
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: packages/web/playwright-report/

  deployability-check:
    needs: [lint, unit-tests, integration-tests, e2e-tests]
    runs-on: ubuntu-latest
    steps:
      - run: echo "✅ All tests passed — deployable"
```

### 4.3 Gate Behavior

- PR cannot merge if any job fails
- `deployability-check` is a synthetic green checkmark; it doesn't run tests itself
- Artifacts (Playwright traces, coverage XML) uploaded only on failure to save storage

---

## 5. Local Usage

```bash
# Full suite (Docker)
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Unit tests only (faster, no Docker needed for backend)
USE_SQLITE_ONLY=true pytest tests/ -m "not integration and not e2e"
pnpm --filter web test:run

# Integration tests only
docker compose -f docker-compose.test.yml up test-runner --abort-on-container-exit

# E2E only
docker compose -f docker-compose.test.yml up web test-runner --abort-on-container-exit
```

---

## 6. New Files Summary

| File | Purpose |
|------|---------|
| `docker-compose.test.yml` | Isolated test environment |
| `tests/integration/conftest.py` | Integration test fixtures |
| `tests/integration/test_auth.py` | Auth integration tests |
| `tests/integration/test_expenses.py` | Expense CRUD integration tests |
| `tests/integration/test_multitenant.py` | Multi-schema isolation tests |
| `tests/integration/test_gateway_routing.py` | Gateway routing tests |
| `packages/web/tests/e2e/` | Playwright E2E specs |
| `packages/web/playwright.config.ts` | Playwright configuration |
| `.github/workflows/test.yml` | CI pipeline |
| `scripts/test-db-setup.sh` | Migration + seed helper |

---

## 7. Skipped (Out of Scope)

- `apps/web` (Next.js) tests — per scope choice A
- Performance/load tests
- Mobile viewport Playwright tests
- Test DB parallelization
- Visual regression testing

---

## 8. Success Criteria

- [ ] `docker compose -f docker-compose.test.yml up` runs green end-to-end locally
- [ ] `.github/workflows/test.yml` passes on PR to main
- [ ] PR cannot merge if any test layer fails
- [ ] Playwright artifacts (screenshots/traces) available on CI failure
- [ ] Unit test coverage for `packages/web` reaches 60%
