Last Updated: 29-05-2026 (14:30)

---
title: "Finance-Tracker Independence Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-25-finance-tracker-independence-design.md"
created: "2026-05-25T20:30:00Z"
status: "draft"
total_phases: 3
estimated_files: 6
task_complexity: "medium"
---

# Finance-Tracker Independence Implementation Plan

## Plan Overview

- **Total phases**: 3
- **Agents involved**: coder, tester
- **Estimated effort**: Medium complexity, focusing on logic porting and path neutralization.

## Dependency Graph

```
Phase 1: Foundation & Logic Porting
    |
    v
Phase 2: CLI Integration & Path Neutralization
    |
    v
Phase 3: Validation & Independence Test
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Config & Maintenance Logic |
| 2     | Phase 2 | Sequential | 1 | main.py & health_check updates |
| 3     | Phase 3 | Sequential | 1 | Final Verification |

## Phase 1: Foundation & Logic Porting

### Objective
Unify configuration and port advanced maintenance logic from Gemini-Manager.

### Agent: coder
### Parallel: No

### Files to Modify

- `packages/core/infrastructure/config.py` — Refactor `get_active_profile` to use `ProfileService`.
- `packages/core/application/maintenance_service.py` — Port SQL parameterization, BOM removal, and cleanup logic.

### Implementation Details
- Ensure `Config` uses `ProfileService` for profile resolution to avoid duplicate logic.
- Port regex-based SQL fixers from `Gemini-Manager/apps/cli/manager/maintenance.py`.
- Add `cleanup_redundant_files` method to `MaintenanceService`.

### Validation
- Unit test `Config.get_active_profile()`.
- Run `MaintenanceService.apply_sql_optimization()` on a dummy SQLite file.

### Dependencies
- Blocked by: None
- Blocks: Phase 2

---

## Phase 2: CLI Integration & Path Neutralization

### Objective
Expose new maintenance features and neutralize hardcoded paths.

### Agent: coder
### Parallel: No

### Files to Modify

- `apps/cli/main.py` — Update `run_maintenance` to call the new logic.
- `scripts/health_check.py` — Enhance `check_hardcoded_paths` and potentially add a `fix` flag.
- `run-gui.bat` — Update port cleanup logic to target 8501.

### Implementation Details
- Update `main.py` argparse to support `maintain --all` or similar if needed.
- Ensure `run-gui.bat` uses the improved port cleanup ported in Phase 1.

### Validation
- `python main.py maintain` executes without errors.
- `scripts/health_check.py` passes all checks.

### Dependencies
- Blocked by: Phase 1
- Blocks: Phase 3

---

## Phase 3: Validation & Independence Test

### Objective
Empirically verify project independence.

### Agent: tester
### Parallel: No

### Implementation Details
- Rename `Gemini-Manager` directory to simulate its absence.
- Run `finance-tracker` CLI and GUI.
- Verify profile switching and maintenance commands still work.

### Validation
- No "File not found" or "Env not set" errors related to external paths.
- All core features functional.

### Dependencies
- Blocked by: Phase 2
- Blocks: None

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `packages/core/infrastructure/config.py` | 1 | Unified config |
| 2 | `packages/core/application/maintenance_service.py` | 1 | Ported logic |
| 3 | `apps/cli/main.py` | 2 | CLI integration |
| 4 | `scripts/health_check.py` | 2 | Validation tool |
| 5 | `run-gui.bat` | 2 | Port cleanup fix |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1 | MEDIUM | Changing core config affects all modules. |
| 2 | LOW | CLI additions are additive. |
| 3 | LOW | Verification only. |

## Execution Profile

```
Execution Profile:
- Total phases: 3
- Parallelizable phases: 0
- Sequential-only phases: 3
- Estimated parallel wall time: N/A
- Estimated sequential wall time: 3 agent turns

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
