---
title: "Backend Resilience Remediation Implementation Plan"
design_ref: "docs/maestro/plans/2026-06-05-backend-resilience-remediation-design.md"
created: "2026-06-05T04:58:00Z"
status: "draft"
total_phases: 3
estimated_files: 5
task_complexity: "medium"
---

# Backend Resilience Remediation Implementation Plan

## Plan Overview

- **Total phases**: 3
- **Agents involved**: `coder`, `tester`
- **Estimated effort**: Targeted fixes for schema duplication, path resolution, and dependency injection to restore backend stability.

## Dependency Graph

```
Phase 1: Consolidate Audit Schema
    |
    v
Phase 2: Fix Backend Connectivity & DI
    |
    v
Phase 3: Update API Endpoint & Verify
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Unify audit_log definition |
| 2     | Phase 2 | Sequential | 1 | Fix imports and service wiring |
| 3     | Phase 3 | Sequential | 1 | Endpoint update and verification |

## Phase 1: Consolidate Audit Schema

### Objective
Unify the `audit_log` schema definition in `schemas.py` and remove redundant initialization logic from `core.py` to prevent "no such column: ts" errors.

### Agent: coder
### Parallel: No

### Files to Modify

- `packages/api/backend/infrastructure/schemas.py` — Update `_ensure_audit_db` to use `Config.BASE_DIR` and ensure `ts` column exists.
- `packages/api/backend/security/core.py` — Remove redundant `_ensure_audit_db` and point `_AUDIT_DB` to `Config.BASE_DIR / "data" / "audit_log.db"`.

### Implementation Details
- Ensure both files reference the same physical `.db` path.
- Remove the `try/except` block that re-creates the table in `core.py`.
- Fix the docstring in `core.py` that incorrectly names the column `timestamp`.

### Validation
- Run `python -m py_compile` on modified files.
- Verify `audit_log.db` is initialized correctly on startup.

### Dependencies
- Blocked by: None
- Blocks: Phase 2

---

## Phase 2: Fix Backend Connectivity & DI

### Objective
Correct the `sys.path` resolution in the stocks router and ensure `DashboardService` is correctly wired in `deps.py`.

### Agent: coder
### Parallel: No

### Files to Modify

- `packages/api/backend/routers/stocks.py` — Update `_STOCK_ANALYZER` path and `sys.path` logic.
- `packages/api/backend/routers/deps.py` — Verify `SqliteVirtualAccountRepository` import and `DashboardService` argument order.

### Implementation Details
- `stocks.py`: Fix path to `apps/cli/stock_analyzer`.
- `deps.py`: Pass `_acc_repo` as the 4th argument to `DashboardService`.

### Validation
- Run `python -m py_compile` on modified files.

### Dependencies
- Blocked by: Phase 1
- Blocks: Phase 3

---

## Phase 3: Update API Endpoint & Verify

### Objective
Update the API server endpoint to pass the active profile ID to the dashboard service and verify the complete fix.

### Agent: tester
### Parallel: No

### Files to Modify

- `packages/api/api_server.py` — Update `get_dashboard` endpoint to resolve `profile_id` via `get_active_profile()`.

### Implementation Details
- Import `get_active_profile` from `deps.py`.
- Pass `profile_id` as the first argument to `dashboard_service.get_summary`.

### Validation
- Start the API server: `python packages/api/api_server.py`.
- Test the endpoint: `curl http://localhost:8000/api/dashboard`.
- Verify no `AttributeError` or `SqliteError` occurs.

### Dependencies
- Blocked by: Phase 2
- Blocks: None

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `packages/api/backend/infrastructure/schemas.py` | 1 | Centralize audit schema |
| 2 | `packages/api/backend/security/core.py` | 1 | Remove redundant audit logic |
| 3 | `packages/api/backend/routers/stocks.py` | 2 | Fix path resolution |
| 4 | `packages/api/backend/routers/deps.py` | 2 | Fix DI wiring |
| 5 | `packages/api/api_server.py` | 3 | Update endpoint & verify |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1 | MEDIUM | Modifying audit schema can cause write failures if out of sync. |
| 2 | LOW | Purely path and wiring fixes. |
| 3 | MEDIUM | Final verification relies on all previous layers working correctly. |

## Execution Profile

```
Execution Profile:
- Total phases: 3
- Parallelizable phases: 0
- Sequential-only phases: 3
- Estimated parallel wall time: N/A
- Estimated sequential wall time: 10-15 minutes

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
