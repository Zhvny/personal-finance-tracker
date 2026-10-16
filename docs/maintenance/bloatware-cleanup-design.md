Last Updated: 29-05-2026 (14:30)

# Design Document: Bloatware Cleanup Strategy

**Date**: 2026-05-28
**Status**: Draft
**Scope**: Finance Tracker Monorepo

## 1. Introduction
The `finance-tracker` project has accumulated significant "bloatware" in the form of transient migration scripts, temporary debugging files, archived documentation, and redundant artifacts. This clutter increases cognitive load for developers, slows down repository operations, and obscures the core codebase. The objective of this cleanup is to streamline the repository to only essential, active, and maintainable files.

## 2. Identification Strategy
Bloatware has been identified based on the following criteria:
- **Transient Utility**: Scripts created for one-time fixes (e.g., `fix_*.py`) or migrations that are now complete.
- **Redundancy**: Files that are superseded by newer versions or exist in root but belong in specialized directories.
- **Archival State**: Documentation and state files from completed Maestro sessions that are no longer relevant to the current system state.
- **Temporary Artifacts**: Test logs, reproduction scripts for closed issues, and transient data results.
- **Binary Bloat**: Large executable files in application directories that should be managed via package managers or environment setup.

## 3. Proposed Deletions

### 3.1 Root Directory
These files are transient fix scripts or temporary test files that clutter the project root.
- `fix_all_imports_v2.py`
- `fix_all_imports.py`
- `fix_api_imports.py`
- `fix_conflicts.py`
- `fix_files.py`
- `fix_imports_v2.py`
- `fix_imports.py`
- `fix_packages_src.py`
- `revert_imports.py`
- `test_write.txt`

### 3.2 Scripts Directory
The following scripts were used for specific database migrations or schema remediations and are no longer required for day-to-day operations.
- `migrate_constraints.py`
- `migrate_data.py`
- `migrate_phase_5.py`
- `patch_sqlite_schema.py`
- `remediate_isolation.py`
- `remediate_schemas.py`

### 3.3 Documentation (Maestro Archives & Reorganization)
- **Archive Cleanup**: Clear archived plans and state files from previous orchestration sessions.
    - `docs/maestro/plans/archive/` (All contents)
    - `docs/maestro/state/archive/` (All contents)
- **Documentation Reorganization**: For each major documentation category, create an `archive/` sub-folder and move files dated before May 2026.
    - Categories: `docs/done/`, `docs/planning/`, `docs/infrastructure/`, `docs/services/`, `docs/task/`, `docs/maintenance/`, `docs/performance/`, `docs/system/`.
    - Criteria: Files with prefix `2026-04-`, `2026-03-`, or earlier, or those explicitly identified as legacy.

### 3.4 Tests & Logs
Temporary reproduction scripts and log files that do not belong in version control.
- `tests/logs/*.log`
- `tests/repro_task16.py`
- `tests/quick_test.py`

### 3.5 Artifacts
- `artifacts/index.html` (Redundant/Transient UI artifact)

### 3.6 Data
- `data/results_honest/` (Transient audit results)
- `data/raw/` (Verify if contents are non-essential/transient; if they contain seed data for specific profiles, they may be moved to `apps/cli/profiles/`)

### 3.7 App-Specific
- `apps/api/prisma-query-engine-windows.exe` (Large binary that should be handled by Prisma's runtime rather than being committed to the repo)

## 4. Preservation List (What Stays)
To ensure system stability and maintainability, the following categories of files will be preserved:
- **Debugging Tools**: Scripts explicitly named `debug_*` (e.g., `scripts/debug_db.py`).
- **Health & Audit**: Core scripts for system health (e.g., `scripts/health_check.py`) and audit log verification (e.g., `scripts/audit_*`).
- **Core Data**: Active databases (e.g., `data/audit_log.db`) and profile-specific data.
- **Setup & Entry Points**: `setup.bat`, `run-cli.bat`, and core application logic.

## 5. Validation Plan
To ensure project integrity post-cleanup, the following steps will be executed:
1. **Environment Setup**: Run `setup.bat` to verify the environment still builds correctly.
2. **Core Entry Check**: Execute `run-cli.bat` to ensure the main application launches.
3. **Test Suite**: Run `pytest tests/unit` to verify that no core logic depended on the deleted files.
4. **Binary Verification**: Verify that `apps/api` functions correctly (Prisma should re-download or use a system-level query engine if configured).

## 6. Rollback Plan
This project uses Git for version control.
- **Immediate Revert**: `git reset --hard HEAD` can be used to restore the repository state if errors are detected before committing.
- **Post-Commit Revert**: `git revert <cleanup-commit-hash>` can be used to roll back the entire cleanup operation if issues are discovered later.
- **Selective Restore**: Specific files can be restored using `git checkout <hash> -- <file-path>`.
