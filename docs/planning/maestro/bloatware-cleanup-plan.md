Last Updated: 29-05-2026 (14:30)

# Implementation Plan: Bloatware Cleanup

**Date**: 2026-05-28
**Status**: Pending Approval
**Design Document**: `docs/maintenance/bloatware-cleanup-design.md`

## 1. Goal
Streamline the `finance-tracker` repository by removing transient scripts, legacy migration tools, archived documentation, and non-essential artifacts. This will reduce repository size, lower cognitive load, and improve maintainability.

---

## 2. Phase 1: Script & Root Cleanup
**Goal**: Remove transient "fix" scripts and completed migration scripts from root and `scripts/`.

- **Root Files**:
    - `fix_all_imports_v2.py`, `fix_all_imports.py`, `fix_api_imports.py`, `fix_conflicts.py`, `fix_files.py`, `fix_imports_v2.py`, `fix_imports.py`, `fix_packages_src.py`, `revert_imports.py`, `test_write.txt`.
- **Scripts Files**:
    - `scripts/migrate_constraints.py`, `scripts/migrate_data.py`, `scripts/migrate_phase_5.py`, `scripts/patch_sqlite_schema.py`, `scripts/remediate_isolation.py`, `scripts/remediate_schemas.py`.
- **Agent Assignment**: `coder`
- **Dependencies**: None

---

## 3. Phase 2: Documentation Reorganization & Cleanup
**Goal**: Clear Maestro archives and reorganize documentation categories.

- **Tasks**:
    - Clear contents of `docs/maestro/plans/archive/` and `docs/maestro/state/archive/`.
    - For each directory in `docs/`: `done/`, `planning/`, `infrastructure/`, `services/`, `task/`, `maintenance/`, `performance/`, `system/`:
        - Create `archive/` sub-directory.
        - Move files dated before May 2026 into the `archive/` folder.
- **Agent Assignment**: `coder`
- **Dependencies**: None

---

## 4. Phase 3: Transient Artifacts & Binary Cleanup
**Goal**: Remove log files, temporary reproduction scripts, large binaries, and legacy databases.

- **Files/Directories**:
    - `tests/logs/*.log`, `tests/quick_test.py`, `tests/repro_task16.py`, `logs/app.log`, `artifacts/index.html`, `data/results_honest/honest_summary.csv`.
    - `apps/api/prisma-query-engine-windows.exe`, `data/raw/`.
    - `results_honest/`, `apps/cli/expense_tracker/data/expense.db`, `apps/cli/investment_tracker/data/portfolio.db`, `apps/finance-tracker-gui/data/merchant_map.db`, `packages/core/infrastructure/data/`.
- **Agent Assignment**: `coder`
- **Dependencies**: None

---

## 5. Phase 4: System Validation
**Goal**: Verify the system remains stable and functional after cleanup.

- **Validation Steps**:
    1. **Environment Integrity**: Run `setup.bat`.
    2. **Application Launch**: Run `run-cli.bat`.
    3. **Core Health**: Run `python scripts/health_check.py`.
    4. **Unit Tests**: Run `pytest tests/unit`.
- **Agent Assignment**: `tester`
- **Dependencies**: Phases 1, 2, 3.

---

## 6. Rollback Procedure
If any critical issues occur:
- `git reset --hard HEAD` (before committing)
- `git revert <cleanup-commit-hash>` (after committing)
