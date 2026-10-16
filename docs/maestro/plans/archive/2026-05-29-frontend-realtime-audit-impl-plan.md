---
title: "Frontend Issues & Real-time Integration Audit Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-29-frontend-realtime-audit-design.md"
created: "2026-05-29T02:45:00Z"
status: "approved"
total_phases: 4
estimated_files: 15
task_complexity: "complex"
---

# Frontend Issues & Real-time Integration Audit Implementation Plan

## Plan Overview

- **Total phases**: 4
- **Agents involved**: design_system_engineer, refactor, coder, tester
- **Estimated effort**: Complex audit of both backend and frontend layers.

## Dependency Graph

```
Phase 1 (UI Foundation) ---+
                           |--> Phase 3 (GUI Fixes) --> Phase 4 (Test)
Phase 2 (Backend Audit) ---+
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | 1, 2   | Parallel  | 2           | UI Foundation + Backend Audit |
| 2     | 3      | Sequential| 1           | GUI State & Boundaries |
| 3     | 4      | Sequential| 1           | Validation |

## Phase 1: Global UI Stability Foundation

### Objective
Establish the root `AppErrorBoundary` to catch unhandled component crashes at the application level.

### Agent: design_system_engineer
### Parallel: Yes

### Files to Create
- `packages/web/src/components/common/ErrorBoundary.jsx` — Universal Error Boundary class component with fallback UI.

### Files to Modify
- `packages/web/src/App.jsx` — Wrap main app entry in `AppErrorBoundary`.

### Validation
- Build `packages/web` and verify intentional crashes are caught by the new boundary.

### Dependencies
- Blocked by: None
- Blocks: Phase 3

## Phase 2: Backend Silent Exception Audit

### Objective
Eliminate 29 `except: pass` blocks in core backend modules and replace with structured logging.

### Agent: refactor
### Parallel: Yes

### Files to Modify
- `apps/cli/stock_analyzer/infrastructure/tui.py`
- `apps/cli/receipt_reader/core/parser.py`
- `apps/cli/investment_tracker/services/stock_service.py`

### Implementation Details
- Replace `pass` with `logger.exception("Descriptive message")`.
- Ensure `logger` is correctly imported and initialized in each file.
- Propagate critical failures using `DataIntegrityError`.

### Validation
- Run `pytest` on affected modules to ensure no regressions in intended behavior.

### Dependencies
- Blocked by: None
- Blocks: Phase 3

## Phase 3: GUI State & Error Boundary Implementation

### Objective
Fix `ReferenceError: setLoading` in `StockAnalyzerContent` and implement component-specific `ButterflyErrorBoundary`.

### Agent: coder
### Parallel: No

### Files to Modify
- `packages/web/src/pages/stock_analyzer.jsx` — Fix `setLoading` reference, implement `ButterflyErrorBoundary` improvements.
- `packages/web/src/finance/TickerContext.jsx` — Expose consistent loading state setters if necessary.

### Implementation Details
- Map `setLoading` to `setBaseLoading` or the appropriate hook setter.
- Ensure `ButterflyMap` fails gracefully with a message instead of a crash.

### Validation
- Navigate to Stock Analyzer page and trigger analysis. Verify no ReferenceErrors.

### Dependencies
- Blocked by: Phase 1, Phase 2
- Blocks: Phase 4

## Phase 4: Validation & Regression Testing

### Objective
Verify error propagation from backend to UI and test boundary fallbacks.

### Agent: tester
### Parallel: No

### Files to Create
- `tests/integration/test_error_handling.py` — Integration test for backend-to-UI error flows.
- `tests/unit/test_ui_boundaries.js` — Unit tests for React Error Boundaries.

### Validation
- Run all new and existing tests. Verify `app.log` contains expected stack traces for failed operations.

### Dependencies
- Blocked by: Phase 3
- Blocks: None

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `packages/web/src/components/common/ErrorBoundary.jsx` | 1 | Global Error Boundary |
| 2 | `packages/web/src/App.jsx` | 1 | App Entry Wrapping |
| 3 | `apps/cli/stock_analyzer/infrastructure/tui.py` | 2 | Backend Audit |
| 4 | `apps/cli/receipt_reader/core/parser.py` | 2 | Backend Audit |
| 5 | `apps/cli/investment_tracker/services/stock_service.py` | 2 | Backend Audit |
| 6 | `packages/web/src/pages/stock_analyzer.jsx` | 3 | GUI Fixes |
| 7 | `packages/web/src/finance/TickerContext.jsx` | 3 | State Management |

## Execution Profile

```
Execution Profile:
- Total phases: 4
- Parallelizable phases: 2 (in 1 batch)
- Sequential-only phases: 2
- Estimated parallel wall time: 3 stages

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
