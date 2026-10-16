Last Updated: 29-05-2026 (14:30)

---
title: "System Remediation and Stabilization"
created: "2026-05-29T00:52:00.000Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# System Remediation and Stabilization Design Document

## Problem Statement
The Finance Tracker system currently has several technical gaps and stabilization issues following a major bloatware cleanup:
1. **Core Implementation Gap**: The `SQLiteInvestmentRepository` lacks implementations for `get_all_lots_by_ticker` and `get_all_sell_transactions_by_ticker`, causing application crashes when accessing investment details.
2. **Environment Fragility**: Hardcoded absolute paths in documentation and automation scripts (`INFRA_AUDIT_LOG.md`, `probe_income.py`, etc.) hinder portability across different developer environments.
3. **Data Pollution**: A residual `qa_financial` profile exists in the `apps/cli/profiles/` directory, causing unit test failures due to unexpected profile detection.
4. **Metadata Non-Compliance**: 93 documentation files are missing mandatory timestamps, violating the project's 'Source of Truth' standards established in `GEMINI.md`.

## Requirements

### Functional Requirements
1. **REPO-FIX**: Implement `get_all_lots_by_ticker` and `get_all_sell_transactions_by_ticker` in `SQLiteInvestmentRepository`.
2. **PATH-FIX**: Replace absolute paths in identified MD and PY files with project-relative paths or environment variables.
3. **DATA-CLEAN**: Permanently delete the `apps/cli/profiles/qa_financial/` directory.
4. **META-FIX**: Inject `dd-mm-yyyy (hh:mm)` timestamps into the 93 identified documentation files to satisfy `GEMINI.md` compliance.

### Non-Functional Requirements
1. **TEST-PASS**: Ensure `pytest tests/unit` passes 100% after remediation.
2. **HEALTH-PASS**: Ensure `scripts/health_check.py` returns `[PASS]` for paths, databases, and timestamps.

### Constraints
- Follow existing ORM/Persistence patterns in `packages/core/infrastructure/investment_tracker/sqlite_repository.py`.
- Adhere to `GEMINI.md` for all documentation and profile standards.

## Approach

### Selected Approach: Strict Remediation
We will perform targeted, surgical fixes for the four identified issues to stabilize the current state without introducing broader changes.

### Decision Matrix
| Criterion | Weight | Strict Remediation | Comprehensive Stabilization |
|-----------|--------|--------------------|-----------------------------|
| Speed of Delivery | 40% | 5: Focused scope | 3: Larger scope |
| Risk of Regression | 30% | 5: Minimal changes | 4: Touches more areas |
| System Health | 30% | 4: Solves key fails | 5: Solves all fails |
| **Weighted Total** | | **4.7** | **3.7** |

## Agent Team

| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1     | coder    | No       | Repository implementation, profile cleanup |
| 2     | refactor | Yes      | Path refactoring, timestamp injection |
| 3     | tester   | No       | Validation (unit tests, health check) |

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Logic error in FIFO lot tracking | MEDIUM | LOW | Verify with `tests/unit/test_investment_logic.py` |
| Accidental profile deletion | HIGH | VERY LOW | Explicitly target only `qa_financial` |
| Timestamp injection corruption | LOW | LOW | Regexp-based injection with verification |

## Success Criteria
1. `SQLiteInvestmentRepository` fully implements the `IInvestmentRepository` interface.
2. `apps/cli/profiles/qa_financial/` is removed from the filesystem.
3. `scripts/health_check.py` reports 0 failures for hardcoded paths and mandatory timestamps.
4. `pytest tests/unit` executes successfully with 100% pass rate.
