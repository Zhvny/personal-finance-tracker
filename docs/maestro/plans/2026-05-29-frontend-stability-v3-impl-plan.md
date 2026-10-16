---
title: "Frontend Issues & Real-time Integration Audit Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-29-frontend-stability-v3-design.md"
created: "2026-05-29T11:45:00Z"
status: "draft"
total_phases: 4
task_complexity: "medium"
---

# Frontend Issues & Real-time Integration Audit Implementation Plan

## Plan Overview
- **Total phases**: 4
- **Agents involved**: coder, tester
- **Estimated effort**: Medium (targeted fixes + testing)

## Dependency Graph
```
Phase 1: Backend Integrity (CLI)
      |
Phase 2: GUI Stability (StockAnalyzer)
      |
Phase 3: Error Boundary Audit
      |
Phase 4: Integration Testing
```

## Execution Strategy
| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Fixes silent failures in CLI. |
| 2     | Phase 2 | Sequential | 1 | Resolves React ReferenceErrors. |
| 3     | Phase 3 | Sequential | 1 | Audits and verifies error boundaries. |
| 4     | Phase 4 | Sequential | 1 | End-to-end validation. |

## Phase 1: Backend Integrity (CLI)
### Objective
Remove silent failures and ensure proper error logging in the CLI main entry to prevent "zombie" states.

### Agent: coder
### Parallel: No

### Files to Modify
- `apps/cli/main.py`: Audit all `except` blocks. Ensure any `pass` is replaced with `logger.exception` unless explicitly justified (e.g., KeyboardInterrupt).

### Validation
- Verify `logs/app.log` captures exceptions when modules fail to launch.
- No bare `except:` or `except Exception: pass` remains.

## Phase 2: GUI Stability (StockAnalyzer)
### Objective
Resolve ReferenceError in `StockAnalyzerContent` and clarify loading states by aligning with `TickerContext`.

### Agent: coder
### Parallel: No

### Files to Modify
- `packages/web/src/pages/stock_analyzer.jsx`: 
  - Rename local `loading` to `baseLoading`.
  - Rename local `setLoading` to `setBaseLoading`.
  - Ensure `useTicker()`'s `loading` (aliased as `tickerLoading`) is correctly handled.

### Validation
- Component renders without `ReferenceError: setLoading is not defined`.
- Verify analysis flow still works correctly with `TickerContext`.

## Phase 3: Error Boundary Audit
### Objective
Verify that graphics-heavy components are properly protected by hierarchical error boundaries.

### Agent: coder
### Parallel: No

### Files to Modify
- `packages/web/src/components/ButterflyMap.jsx`: Confirm usage of `ButterflyErrorBoundary`.
- `packages/web/src/App.jsx`: Confirm `AppErrorBoundary` coverage for all lazy-loaded modules.

### Validation
- Simulate an error in `ButterflyMap` and verify the boundary catches it without crashing the entire app.

## Phase 4: Integration Testing
### Objective
Verify end-to-end error propagation and UI stability through automated tests.

### Agent: tester
### Parallel: No

### Files to Create
- `tests/integration/test_error_handling.py`: Test that CLI errors are correctly logged.
- `tests/unit/test_ui_boundaries.js`: (Mock test) Verify React boundaries catch component errors.

### Validation
- Run all new tests and confirm they pass.
