Last Updated: 29-05-2026 (14:30)

# Documentation Restructuring & README Overhaul Design

**Date**: 28-05-2026
**Status**: APPROVED

## 1. Goal
Organize ('rapihkan') the documentation structure by archiving old session/task data and overhaul the root `README.md` to serve as a high-quality entry point for the monorepo.

## 2. Archiving Strategy
- **Per-folder Archive**: Create `archive/` subdirectories within:
    - `docs/done/`
    - `docs/planning/`
    - `docs/plan/`
    - `docs/task/`
    - `docs/maestro_session/`
- **Criteria**: Move files older than May 2026 or completed task reports that are not part of the "Authoritative Hubs".

## 3. Documentation Hubs (SSOT Sync)
Synchronize `GEMINI.md` and `README.md` to point to these specific authoritative files:
- **Product Manual**: `docs/system/product-manual.md`
- **Architecture Blueprint**: `docs/system/architecture.md`
- **Master Plan**: `docs/planning/MASTER_PLAN_REFINED.md`
- **Maintenance Guide**: `docs/maintenance/maintenance.md`

## 4. README.md Overhaul
- **Hero Section**: Retain title and version.
- **Project Structure**: Add a visual tree explaining the monorepo (apps, packages, docs).
- **Tech Stack**: Detail the core technologies (Python, React, SQLite, OCR Ensemble).
- **Quick Start**: Clear steps for installation (`setup.bat`) and execution (`run-cli.bat`, `run-gui.bat`).
- **Documentation Map**: Logical grouping of links to the Hubs and service-specific docs.

## 5. Metadata & Consistency
- Ensure all updated docs include the timestamp `28-05-2026`.
- Clean up any redundant or broken links identified during the process.
