---
title: "Portfolio FX Integrity & API Fix (Revised) Implementation Plan"
design_ref: "docs/maestro/plans/2026-06-01-portfolio-api-fix-design.md"
created: "2026-06-01T17:45:00Z"
status: "draft"
total_phases: 3
estimated_files: 10
task_complexity: "medium"
---

# Portfolio FX Integrity & API Fix (Revised) Implementation Plan

## Plan Overview

- **Total phases**: 3
- **Agents involved**: `coder`, `tester`
- **Estimated effort**: Medium. Focuses on resolving a persistent `ModuleNotFoundError` in the API and fixing deep valuation logic bugs for long-term holdings and Gold.

## Dependency Graph

```
Phase 1: API Entry & Module Fix (coder)
    |
    v
Phase 2: Valuation Logic Audit & Gold Pricing Fix (tester)
    |
    v
Phase 3: Persistence & UI Integration Cleanup (coder)
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Fix imports and env |
| 2     | Phase 2 | Sequential | 1 | Audit & Logic Fix |
| 3     | Phase 3 | Sequential | 1 | Final Integration |

---

## Phase 1: API Entry & Module Fix

### Objective
Resolve the `ModuleNotFoundError` for `PostgresFXRepository` and ensure the API server correctly resolves modules in the monorepo structure.

### Agent: coder
### Parallel: No

### Files to Modify

- `packages/api/backend/routers/deps.py` — Ensure imports are robust and PYTHONPATH is handled.
- `packages/api/api_server.py` — Add explicit sys.path manipulation if necessary for standard deployments.

### Implementation Details
- Standardize on `from packages.core...` imports.
- Verify that `PYTHONPATH` includes the project root.
- Fix any remaining relative imports that break when running from `packages/api`.

### Validation
- `python -c "from packages.core.infrastructure.persistence.postgres_fx_repository import PostgresFXRepository"`
- Start the API server locally: `python packages/api/api_server.py` (check for immediate crashes).

---

## Phase 2: Valuation Logic Audit & Gold Pricing Fix

### Objective
Audit `InvestmentService.refresh_prices` and `get_active_investments` to ensure Gold and Commodities use accurate current market data and that FX gain vs. Capital gain is calculated correctly.

### Agent: tester
### Parallel: No

### Files to Modify
- `packages/core/application/investment_service.py` — Fix Gold per-gram conversion and stale price fallbacks.
- `packages/core/utils/symbol_utils.py` — Ensure aliases for GOLD/XAU are perfectly mapped.

### Implementation Details
- **Gold Fix**: Ensure `GC=F` (Ounce) is correctly converted to grams AND priced in IDR using Live FX.
- **Stale Price Logic**: If `refresh_prices` fails, the system must NOT fallback to a value that implies 0% gain if a historical snapshot exists.
- **P/L Decomposition**: Verify that `fx_gain` correctly reflects the movement of USD/IDR from buy-date to current-date.

### Validation
- Create a reproduction script `scripts/verify_gold_valuation.py` that mocks a Gold purchase 3 years ago and compares it to today's price.
- Assert that `curr_value` is NOT equal to `buy_value` if market price has moved.

---

## Phase 3: Persistence & UI Integration Cleanup

### Objective
Ensure all valuation results are persisted correctly in PostgreSQL and that the UI (CLI/Web) receives the 'is_stale' flag and correct gain breakdowns.

### Agent: coder
### Parallel: No

### Files to Modify
- `packages/core/infrastructure/persistence/postgres_investment_repository.py` — Ensure `historical_prices` (snapshots) are saved and retrieved efficiently.
- `packages/api/backend/routers/investments.py` — Ensure the API endpoint returns the full breakdown (cap_gain, fx_gain, is_stale).

### Validation
- Run `refresh_prices` and verify that `investment.historical_prices` table in Postgres is updated.
- `curl http://localhost:8000/api/investments` and verify the JSON contains the new P/L fields.

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `packages/api/backend/routers/deps.py` | 1 | Import fix |
| 2 | `packages/api/api_server.py` | 1 | Entry point fix |
| 3 | `packages/core/application/investment_service.py` | 2 | Valuation logic fix |
| 4 | `packages/core/utils/symbol_utils.py` | 2 | Ticker aliases |
| 5 | `packages/core/infrastructure/persistence/postgres_investment_repository.py` | 3 | Persistence fix |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1 | LOW | Standard import fixes. |
| 2 | HIGH | Financial math logic is sensitive; small errors in Gold conversion or FX timing lead to massive valuation gaps. |
| 3 | MEDIUM | Database schema must match the Pydantic models exactly. |

## Execution Profile

```
Execution Profile:
- Total phases: 3
- Parallelizable phases: 0
- Sequential-only phases: 3
- Estimated parallel wall time: 3 turns
- Estimated sequential wall time: 3 turns

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
