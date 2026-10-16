---
title: "Bulk OCR Import Refactor"
created: "2026-05-30T10:00:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Bulk OCR Import Refactor Design Document

## Problem Statement
The bulk OCR import task for 11 expense and investment images is currently blocked by three critical issues:
1. **Gemini API Access**: All existing Gemini API keys are returning 403 Forbidden errors.
2. **Database Integrity**: The PostgreSQL sequence for the `expenses` table is out of sync, causing primary key collisions.
3. **Script Incompatibility**: The `batch_import_images.py` script is hardcoded for Gemini and has monorepo pathing issues.

## Requirements
1. **OCR Engine**: Transition from Gemini to the project's existing `OCREnsemble` (Tesseract + EasyOCR + PaddleOCR).
2. **Data Scope**: Support extraction for both **Expense** and **Investment** transaction types.
3. **Database Stability**: Synchronize PostgreSQL sequences before import.
4. **Monorepo Compatibility**: Use absolute imports and follow project directory conventions.

## Approach
### Selected Approach: Ensemble-Powered Local Import
- **OCR**: Integrate `OCREnsemble` from `apps/cli/receipt_reader` into a revised `batch_import_images.py`.
- **Database**: Execute `SELECT setval('financials.expenses_id_seq', (SELECT max(id) FROM financials.expenses))` pre-import.
- **Pathing**: Standardize on absolute `packages.*` imports.

### Decision Matrix
| Criterion | Weight | Gemini OCR | Ensemble OCR (Local) |
|-----------|--------|------------|-----------------------|
| Reliability | 40% | 1 (Blocked) | 5 (Always available) |
| Accuracy | 30% | 5 (High) | 4 (High with ensemble) |
| Setup Ease | 20% | 5 (API call) | 3 (Local engines req) |
| Cost | 10% | 3 (API quota) | 5 (Free/Local) |
| **Weighted Total** | | **2.6** | **4.3** |

## Agent Team
| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1     | debugger | No       | DB Sequence Fix & Environment Validation |
| 2     | refactor | No       | `batch_import_images.py` refactor to Ensemble OCR |
| 3     | coder    | No       | Final Bulk Import Execution |

## Risk Assessment
| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Local OCR Accuracy | MEDIUM | MEDIUM | Use `OCREnsemble` field-level voting. |
| DB Sequence Drift | LOW | LOW | Mandatory pre-import sequence reset. |
| Missing OCR Deps | MEDIUM | LOW | Pre-flight check for tesseract/easyocr/paddleocr. |

## Success Criteria
1. 11 images (4 Expense, 7 Investment) successfully processed and archived.
2. 11 records created in respective databases (SQLite for expenses, Postgres for investments).
3. No primary key collisions in PostgreSQL.
