---
session_id: "2026-05-29-fix-active-session-plan-v3"
task: "fix/lanjutin ini plan, Problem Statement → Yes, Selected Approach → Yes, Risk Assessment → Yes active-session.md"
complexity: "medium"
design_document: "docs/maestro/plans/2026-05-29-fix-active-session-plan-v3-design.md"
---

# Implementation Plan: Frontend Issues & Real-time Integration Audit (Fixed v3)

Fix silent failures in backend, resolve loading state issues in GUI, and implement robust error boundaries.

## Phase 1: Backend Audit - main.py Visibility
- **Agent**: `coder`
- **Goal**: Remove silent error swallowing in the primary CLI entry point.
- **Files**:
  - `apps/cli/main.py`
- **Actions**:
  - Search for `except: pass` or `except Exception: pass`.
  - Replace with proper `logger.exception` and appropriate error handling/propagation.
  - Ensure all critical loops have error logging.

## Phase 2: GUI Fix - StockAnalyzerContent Loading State
- **Agent**: `coder`
- **Blocked by**: Phase 1
- **Goal**: Resolve loading state ReferenceErrors and synchronize with TickerContext.
- **Files**:
  - `packages/web/src/pages/stock_analyzer.jsx`
- **Actions**:
  - Audit `StockAnalyzerContent` for references to `setLoading`.
  - Migrate to `setBaseLoading` or the established loading pattern from `TickerContext`.
  - Verify prop-drilling or context-usage consistency.

## Phase 3: UX - ButterflyMap Error Boundaries
- **Agent**: `coder`
- **Blocked by**: Phase 2
- **Goal**: Protect main UI from crashes in complex visualization components.
- **Files**:
  - `packages/web/src/components/ButterflyMap.jsx`
  - `packages/web/src/components/ButterflyErrorBoundary.jsx`
- **Actions**:
  - Create `ButterflyErrorBoundary` if it doesn't exist, or refine existing one.
  - Wrap `ButterflyMap` export or internal render with the boundary.
  - Implement a fallback UI (e.g., "Visualization Unavailable") for data anomalies.

## Phase 4: Validation - End-to-End Error Testing
- **Agent**: `tester`
- **Blocked by**: Phase 3
- **Goal**: Verify that backend errors propagate and UI boundaries catch failures.
- **Files**:
  - `tests/integration/test_error_handling.py`
  - `tests/unit/test_ui_boundaries.js`
- **Actions**:
  - Write backend integration test that triggers a handled exception in `main.py` logic.
  - Write UI unit test that simulates a crash in `ButterflyMap` and asserts fallback UI visibility.
