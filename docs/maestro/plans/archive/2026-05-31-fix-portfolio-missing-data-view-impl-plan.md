---
title: "Fix Missing Data in VIEW_PORTFOLIO Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-31-fix-portfolio-missing-data-view-design.md"
created: "2026-05-31T00:25:00Z"
status: "approved"
total_phases: 2
estimated_files: 2
task_complexity: "medium"
---

# Fix Missing Data in VIEW_PORTFOLIO Implementation Plan

## Plan Overview

- **Total phases**: 2
- **Agents involved**: coder, tester
- **Estimated effort**: Medium. Refactoring data mapping and fetch logic with verification.

## Dependency Graph

```
Phase 1: Implementation (Repo & Main)
    |
Phase 2: Verification (Display Tests)
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Refactor Core Logic |
| 2     | Phase 2 | Sequential | 1 | Verify UI Display |

## Phase 1: Data Logic Refactor

### Objective
Ensure `Investment` model always has `buy_price_idr` and `PortfolioApp` always returns valid price data for UI.

### Agent: coder
### Parallel: No

### Files to Modify

- `packages/core/infrastructure/investment_tracker/sqlite_repository.py` — Update `_map_row_to_investment` to calculate `buy_price_idr` if missing.
- `apps/cli/investment_tracker/main.py` — Refactor `_fetch_prices` to return a complete dict even on fetch failure.

### Implementation Details

1. **Repository**: In `_map_row_to_investment`, use `FXService` (or a static rate if service not available) to populate `buy_price_idr` for existing investments.
2. **Main**: In `_fetch_prices`, catch exceptions and return a dict with `buy_price_idr` as the `current_price_idr` fallback, marking `stale=True`.

### Validation

- Unit test for repository mapping.
- Verify `PortfolioApp` doesn't return `None` in `_fetch_prices` during a simulated network failure.

### Dependencies

- Blocked by: None
- Blocks: Phase 2

---

## Phase 2: UI Verification

### Objective
Verify that `VIEW_PORTFOLIO` correctly displays numeric data even when market prices are stale.

### Agent: tester
### Parallel: No

### Files to Modify
- `tests/integration/test_portfolio_view.py` (Create) — Integration test to verify table output.

### Implementation Details
1. Mock `StockPriceService` to fail.
2. Run `PortfolioApp.view_portfolio` and capture output.
3. Assert that QTY and BUY_PRICE columns are populated with valid numbers instead of "—".

### Validation
- All integration tests pass.

### Dependencies
- Blocked by: Phase 1
- Blocks: None

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `packages/core/infrastructure/investment_tracker/sqlite_repository.py` | 1 | Fix domain model mapping |
| 2 | `apps/cli/investment_tracker/main.py` | 1 | Fix price fetch fallbacks |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1     | MEDIUM | Modifies core repository mapping; must ensure no regression in other features. |
| 2     | LOW | Purely verification. |

## Execution Profile

```
Execution Profile:
- Total phases: 2
- Parallelizable phases: 0
- Sequential-only phases: 2
- Estimated parallel wall time: N/A
- Estimated sequential wall time: ~10 mins

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
