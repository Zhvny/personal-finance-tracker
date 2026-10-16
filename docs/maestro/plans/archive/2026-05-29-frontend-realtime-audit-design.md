---
title: "Frontend Issues & Real-time Integration Audit"
created: "2026-05-29T02:40:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "complex"
---

# Frontend Issues & Real-time Integration Audit Design Document

## Problem Statement

The Finance Tracker system suffers from critical reliability and observability gaps across its full stack:

1. **Backend Silent Failures**: 29 instances of `except: pass` in core modules (`apps/cli/stock_analyzer/`, `receipt_reader/`, `investment_tracker/`) swallow technical errors. This leads to "zombie" states where the GUI/CLI appears functional but data remains stale or incorrect without alerting the user.
2. **GUI ReferenceErrors**: The `StockAnalyzerContent` component incorrectly references `setLoading`, which is not declared in its scope or provided by `useTicker`. This causes UI crashes when analysis actions are triggered.
3. **Weak Error Boundaries**: Graphics-heavy components like the `ButterflyMap` rely on local, component-specific boundaries. A failure in data sanitization or websocket streaming can still crash the parent page due to a lack of a robust, hierarchical error handling strategy.

## Requirements

### Functional Requirements

1. **REQ-1 (Backend Visibility)**: Replace all 29 `except: pass` blocks with structured logging (`logger.exception`) and propagate errors to trigger user-facing alerts.
2. **REQ-2 (GUI Fix)**: Resolve the `ReferenceError` in `StockAnalyzerContent` by properly mapping state (e.g., using `setBaseLoading`).
3. **REQ-3 (Stability)**: Implement a global `AppErrorBoundary` and enhance `ButterflyErrorBoundary` to provide graceful fallbacks.

### Non-Functional Requirements

1. **REQ-4 (Traceability)**: All backend errors must be logged to `logs/app.log`.
2. **REQ-5 (Minimal Impact)**: UI fixes must not break existing `TickerContext` consumers.

### Constraints

- Adhere to existing Python logging standards and React functional component patterns.

## Approach

### Selected Approach: Pragmatic Hierarchical Audit

1. **Backend**: Surgical replacement of `except: pass` with structured logging and propagation of `DataIntegrityError`.
2. **GUI**: Implementation of a root `AppErrorBoundary` and refactoring of `StockAnalyzerContent` to use consistent state management.

### Decision Matrix

| Criterion | Weight | Pragmatic Audit | Full Refactor |
|-----------|--------|-----------------|---------------|
| REQ-1 (Backend Visibility) | 30% | 5 | 5 |
| REQ-2 (GUI Fix) | 20% | 5 | 5 |
| REQ-3 (Stability) | 30% | 4 | 5 |
| REQ-5 (Minimal Impact) | 20% | 5 | 1 |
| **Weighted Total** | | **4.7** | **3.9** |

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Log Flooding | MEDIUM | MEDIUM | Throttled logger or high-frequency loop checks. |
| Graphic Breakage | MEDIUM | LOW | Dev-mode stack traces in boundaries. |
| WhaleActivity Regression | LOW | MEDIUM | Variable shadow check. |
| Circular Error Deps | HIGH | LOW | Dependency-free React class for Root Boundary. |

## Success Criteria

1. Zero instances of `except: pass` in target modules.
2. `StockAnalyzerContent` renders and analyzes without `ReferenceError`.
3. Intentional component crashes (tested via debug harness) are caught by boundaries with fallback UI.
