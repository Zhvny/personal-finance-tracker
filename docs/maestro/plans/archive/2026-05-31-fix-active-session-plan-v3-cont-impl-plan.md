---
title: "Frontend Issues & Real-time Integration Audit (Finalization) Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-31-fix-active-session-plan-v3-cont-design.md"
created: "2026-05-31T16:25:00Z"
status: "draft"
total_phases: 4
estimated_files: 6
task_complexity: "medium"
---

# Frontend Issues & Real-time Integration Audit (Finalization) Implementation Plan

## Plan Overview

- **Total phases**: 4
- **Agents involved**: `coder`, `tester`
- **Estimated effort**: Medium. Focuses on backend logging precision, frontend loading state synchronization, and robust error boundaries.

## Dependency Graph

```
Phase 1: Backend Audit [coder]
    │
    ▼
Phase 2: GUI Loading Sync [coder]
    │
    ▼
Phase 3: UX Stability Boundaries [coder]
    │
    ▼
Phase 4: Validation [tester]
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Backend Reliability |
| 2     | Phase 2 | Sequential | 1 | GUI State Sync |
| 3     | Phase 3 | Sequential | 1 | UI Resilience |
| 4     | Phase 4 | Sequential | 1 | Verification |

## Phase 1: Backend Reliability Audit

### Objective
Eliminate silent failures and upgrade logging precision in CLI backend to ensure full traceability of "zombie" states.

### Agent: coder
### Parallel: No

### Files to Modify

- `apps/cli/main.py` — Audit for `except` blocks using `print` or `logger.error` without `logger.exception`.
- `apps/cli/scheduler.py` — Upgrade `logger.error` to `logger.exception` in `run_monthly_optimization` and Senate Evaluation blocks.
- `apps/cli/investment_tracker/services/stock_service.py` — Replace `except: pass` in `get_current_price_usd` with `logger.exception`.

### Implementation Details
- Standardize all exception handling to include full tracebacks via `logger.exception`.
- Ensure critical background loops (like FX rate fetching) have meaningful fallback logging.

### Validation
- `python apps/cli/main.py --help` (Smoke test)
- Manual check of `logs/app.log` after triggering a mocked failure.

### Dependencies
- Blocked by: None
- Blocks: Phase 2

---

## Phase 2: GUI Loading Synchronization

### Objective
Ensure the Stock Analyzer loading state is perfectly synchronized with TickerContext to prevent UI flickering and inconsistent analysis feedback.

### Agent: coder
### Parallel: No

### Files to Modify

- `packages/web/src/pages/stock_analyzer.jsx` — Finalize `baseLoading` and `tickerLoading` integration.

### Implementation Details
- Ensure `StockAnalyzerContent` correctly shows `StockAnalyzerSkeleton` when `baseLoading` is true.
- Synchronize sub-component loaders (`SenateAgent`, `WhaleActivity`) if their independent states cause visual layout shift.

### Validation
- Run `node packages/web/tests/test_ui_loading_state.js`
- Manual verification of page transition during analysis triggers.

### Dependencies
- Blocked by: Phase 1
- Blocks: Phase 3

---

## Phase 3: UX Stability Boundaries

### Objective
Finalize `ButterflyErrorBoundary` features to provide graceful fallbacks and debugging info during graphics engine stalls.

### Agent: coder
### Parallel: No

### Files to Modify

- `packages/web/src/components/ButterflyErrorBoundary.jsx` — Add "Copy Error" debug feature and ensure `message` prop usage.

### Implementation Details
- Add a small `IconCopy` button inside the error boundary fallback for developer debugging.
- Verify that `ButterflyMap` export remains wrapped correctly.

### Validation
- Manual trigger of a JS error inside `ButterflyMapContent` and verification of fallback UI.

### Dependencies
- Blocked by: Phase 2
- Blocks: Phase 4

---

## Phase 4: Validation

### Objective
Empirically verify error propagation and UI resilience through automated integration and unit checks.

### Agent: tester
### Parallel: No

### Files to Create
- `packages/web/tests/test_ui_boundaries.js` — New UI boundary test script.

### Files to Modify
- `tests/integration/test_error_handling.py` — Add case for `ButterflyService` failure visibility.

### Validation
- `pytest tests/integration/test_error_handling.py`
- `node packages/web/tests/test_ui_boundaries.js`

### Dependencies
- Blocked by: Phase 3
- Blocks: None

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `apps/cli/main.py` | 1 | Backend Logging |
| 2 | `apps/cli/scheduler.py` | 1 | Scheduler Traceability |
| 3 | `apps/cli/investment_tracker/services/stock_service.py` | 1 | Silent Failure Fix |
| 4 | `packages/web/src/pages/stock_analyzer.jsx` | 2 | Loading Sync |
| 5 | `packages/web/src/components/ButterflyErrorBoundary.jsx` | 3 | Error UI |
| 6 | `tests/integration/test_error_handling.py` | 4 | Integration Test |
| 7 | `packages/web/tests/test_ui_boundaries.js` | 4 | UI Test |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1 | LOW | Standard logging changes, low regression risk. |
| 2 | MEDIUM | Complex React state synchronization might affect render cycles. |
| 3 | LOW | UI boundary is isolated. |
| 4 | LOW | Read-only verification. |

## Execution Profile

```
Execution Profile:
- Total phases: 4
- Parallelizable phases: 0
- Sequential-only phases: 4
- Estimated parallel wall time: N/A
- Estimated sequential wall time: ~45 mins

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
