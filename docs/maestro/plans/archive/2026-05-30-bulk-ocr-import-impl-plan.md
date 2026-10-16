---
title: "Bulk OCR Import Refactor Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-30-bulk-ocr-import-design.md"
created: "2026-05-30T10:15:00Z"
status: "draft"
total_phases: 3
estimated_files: 2
task_complexity: "medium"
---

# Bulk OCR Import Refactor Implementation Plan

## Plan Overview
- **Total phases**: 3
- **Agents involved**: debugger, refactor, coder
- **Estimated effort**: Medium complexity due to local OCR integration and database troubleshooting.

## Dependency Graph
```
Phase 1: DB Fix & Env Validation
    |
Phase 2: Script Refactor (Ensemble OCR)
    |
Phase 3: Final Bulk Import Execution
```

## Execution Strategy
| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Environment setup |
| 2     | Phase 2 | Sequential | 1 | Code refactoring |
| 3     | Phase 3 | Sequential | 1 | Data import |

---

## Phase 1: Environment & DB Fix
### Objective
Synchronize PostgreSQL sequences to prevent primary key collisions and verify OCR dependencies.

### Agent: debugger
### Parallel: No

### Implementation Details
1. Execute `SELECT setval('financials.expenses_id_seq', (SELECT max(id) FROM financials.expenses))` in PostgreSQL.
2. Verify that `tesseract`, `easyocr`, and `paddleocr` are correctly installed and reachable in the environment.

### Validation
- No errors when inserting a dummy expense record into Postgres.
- `tesseract --version` and python imports for `easyocr`/`paddleocr` pass.

### Dependencies
- Blocked by: None
- Blocks: Phase 2, Phase 3

---

## Phase 2: Script Refactor (Ensemble OCR)
### Objective
Refactor `scripts/batch_import_images.py` to use local `OCREnsemble` instead of Gemini.

### Agent: refactor
### Parallel: No

### Files to Modify
- `scripts/batch_import_images.py` — Replace Gemini extraction logic with `OCREnsemble` and `ReceiptParser`. Fix absolute import paths.

### Implementation Details
1. Import `OCREnsemble` from `apps.cli.receipt_reader.core.ocr_ensemble`.
2. Update `process_image` to use `ensemble.run(file_path)` and `parser.parse_all(text)`.
3. Standardize all project-level imports to use absolute `packages.*` paths.
4. Ensure the script correctly handles both Expense and Investment logic using the ensemble's output.

### Validation
- Run script on a single test image and verify successful DB entry.

### Dependencies
- Blocked by: Phase 1
- Blocks: Phase 3

---

## Phase 3: Final Bulk Import Execution
### Objective
Execute the bulk import for the 11 staged images.

### Agent: coder
### Parallel: No

### Implementation Details
1. Ensure all 11 images are present in `images/New/`.
2. Run `python scripts/batch_import_images.py`.
3. Confirm that all images are moved to `images/Archive/` upon success.
4. Verify record counts in `portfolio.db` (Personal profile) and PostgreSQL `financials.expenses`.

### Validation
- `images/New/` is empty.
- `images/Archive/` contains the 11 processed images.
- Database queries confirm 11 new records with today's date.

### Dependencies
- Blocked by: Phase 2
- Blocks: None

---

## File Inventory
| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `scripts/batch_import_images.py` | 2 | Primary import logic |

## Risk Classification
| Phase | Risk | Rationale |
|-------|------|-----------|
| 1 | LOW | Straightforward DB sequence fix. |
| 2 | MEDIUM | Complex dependency integration (OCREnsemble). |
| 3 | LOW | Execution of validated script. |

## Execution Profile
```
Execution Profile:
- Total phases: 3
- Parallelizable phases: 0
- Sequential-only phases: 3
- Estimated sequential wall time: 15-20 minutes
```
