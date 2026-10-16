---
title: "Frontend Issues & Real-time Integration Audit (Continuation)"
created: "2026-05-31T16:15:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Frontend Issues & Real-time Integration Audit (Continuation) Design Document

## Problem Statement

The Finance Tracker system suffers from critical reliability and observability gaps across its full stack:

1. **Backend Silent Failures**: Instances of `except: pass` in core modules swallow technical errors. While some modules have been audited, `apps/cli/main.py` still contains silent failures that lead to "zombie" states.
2. **GUI ReferenceErrors**: The `StockAnalyzerContent` component incorrectly referenced `setLoading`. While a fix using `setBaseLoading` has been partially implemented, it needs final verification and alignment with `TickerContext`.
3. **Weak Error Boundaries**: Graphics-heavy components like `ButterflyMap` need robust, hierarchical error handling to prevent parent page crashes during data anomalies.

## Requirements

### Functional Requirements
1. **REQ-1 (Backend Visibility)**: Remove all remaining `except: pass` blocks in `apps/cli/main.py` and replace them with `logger.exception` and proper error propagation.
2. **REQ-2 (GUI Fix)**: Verify and finalize the `setBaseLoading` implementation in `StockAnalyzerContent`.
3. **REQ-3 (Stability)**: Ensure `ButterflyErrorBoundary` provides graceful fallbacks for `ButterflyMap`.
4. **REQ-4 (Validation)**: Implement integration and unit tests to verify end-to-end error propagation and boundary behavior.

### Non-Functional Requirements
1. **REQ-5 (Traceability)**: All backend errors must be logged to `logs/app.log`.
2. **REQ-6 (Minimal Impact)**: UI fixes must not break existing `TickerContext` consumers.

## Approach

### Selected Approach: Pragmatic Completion & Validation

1. **Reconciliation**: Audit and fix `apps/cli/main.py` for silent failures.
2. **Verification**: Finalize the partial GUI fixes in `StockAnalyzerContent`.
3. **Validation**: Create `tests/integration/test_error_handling.py` and `packages/web/tests/test_ui_boundaries.js`.

## Architecture

### Component Diagram
```
[Backend]
apps/cli/main.py --> Logger --> logs/app.log

[Frontend]
StockAnalyzer (Page)
  └── TickerContext (State)
  └── StockAnalyzerContent (Logic)
        └── ButterflyErrorBoundary (Safety)
              └── ButterflyMap (Viz)
```

### Data Flow
1. **Error Flow**: Exceptions in `main.py` are caught by the top-level loop, logged with full stack traces to `app.log`, and surfaced to the CLI UI instead of silent failure.
2. **Loading Flow**: `StockAnalyzerContent` consumes `baseLoading` from `TickerContext`. `setBaseLoading` is used to synchronize the UI state during asynchronous fetches.
3. **Boundary Flow**: If `ButterflyMap` encounters a rendering error, the `ButterflyErrorBoundary` catches the crash and renders a "Visualization Unavailable" fallback.

### Key Interfaces
- `Logger.exception(msg, *args, **kwargs)`: Standardized backend error reporting.
- `useTickerContext()`: Hook providing `{ baseLoading, setBaseLoading }`.
- `ButterflyErrorBoundary(children, fallbackMessage)`: Safety wrapper.

## Agent Team

| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1     | `coder`  | No       | Fixed `apps/cli/main.py` with proper logging |
| 2     | `coder`  | No       | Verified `StockAnalyzerContent` loading logic |
| 3     | `coder`  | No       | `ButterflyErrorBoundary` and wrapped `ButterflyMap` |
| 4     | `tester` | No       | Integration and unit tests for error handling |

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Log Flooding | MEDIUM | MEDIUM | Throttled logger or high-frequency loop checks. |
| Graphic Breakage | MEDIUM | LOW | Dev-mode stack traces in boundaries. |
| Test Environment Drift | LOW | MEDIUM | Use mocked websocket data for UI tests. |

## Success Criteria

1. **Backend Integrity**: Static analysis or manual audit confirms zero instances of `except: pass` in `apps/cli/main.py`.
2. **GUI Stability**: `StockAnalyzerContent` renders and transitions without `ReferenceError`.
3. **Resilience**: A simulated crash in `ButterflyMap` results in a visible fallback UI.
4. **Observability**: Integration tests verify backend errors appear in `logs/app.log`.
