---
title: "Frontend Issues & Real-time Integration Audit (Fixed v4) Implementation Plan"
design_ref: "docs/maestro/plans/2026-06-01-fix-active-session-v4-design.md"
created: "2026-06-01T16:40:00Z"
status: "approved"
total_phases: 4
estimated_files: 4
task_complexity: "medium"
---

# Frontend Issues & Real-time Integration Audit (Fixed v4) Implementation Plan

## Plan Overview
- **Total phases**: 4
- **Agents involved**: `coder`, `tester`
- **Estimated effort**: Medium. Focuses on backend audit, GUI state fix, and boundary verification.

## Dependency Graph
```
Phase 1 (Backend Audit)
  │
  ├─ Phase 2 (GUI Fix) ──┐
  │                      ├─ Phase 4 (Validation)
  └─ Phase 3 (UX Audit) ─┘
```

## Execution Strategy
| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Foundation audit |
| 2     | Phase 2, 3 | Parallel | 2 | Concurrent GUI/UX work |
| 3     | Phase 4 | Sequential | 1 | Final validation |

---

## Phase 1: Backend Audit - main.py Visibility
### Objective
Remove silent error swallowing in `apps/cli/main.py`.

### Agent: `coder`
### Parallel: No

### Files to Modify
- `apps/cli/main.py` — Audit all `try/except` blocks.

### Implementation Details
- Ensure all `except Exception:` blocks call `logger.exception`.
- Remove any `except: pass` if found.

### Validation
- Run `python apps/cli/main.py --dashboard` (verify it runs without crashing).

---

## Phase 2: GUI Fix - StockAnalyzerContent Loading State
### Objective
Resolve loading state `ReferenceError` and synchronize with `TickerContext`.

### Agent: `coder`
### Parallel: Yes

### Files to Modify
- `packages/web/src/pages/stock_analyzer.jsx`

### Implementation Details
- Audit `StockAnalyzerContent` for references to `setLoading`.
- Align with `setBaseLoading` or the established pattern from `TickerContext`.

### Validation
- Verify page renders and loads without console errors.

---

## Phase 3: UX - ButterflyMap Error Boundaries Verification
### Objective
Verify and refine error recovery for the `ButterflyMap` component.

### Agent: `coder`
### Parallel: Yes

### Files to Modify
- `packages/web/src/components/ButterflyMap.jsx`
- `packages/web/src/components/ButterflyErrorBoundary.jsx`

### Implementation Details
- Verify `ButterflyErrorBoundary` is properly catching and rendering a fallback.
- Refine the fallback UI if it is too sparse.

### Validation
- Simulate a crash in `ButterflyMap` to confirm boundary catch.

---

## Phase 4: Validation - End-to-End Error Testing
### Objective
Verify end-to-end error propagation and boundary behavior.

### Agent: `tester`
### Parallel: No

### Files to Create
- `tests/integration/test_error_handling.py`

### Validation
- Run `pytest tests/integration/test_error_handling.py`.

---

## File Inventory
| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `apps/cli/main.py` | 1 | Backend audit |
| 2 | `packages/web/src/pages/stock_analyzer.jsx` | 2 | GUI fix |
| 3 | `packages/web/src/components/ButterflyMap.jsx` | 3 | UI boundary |
| 4 | `tests/integration/test_error_handling.py` | 4 | Integration test |
