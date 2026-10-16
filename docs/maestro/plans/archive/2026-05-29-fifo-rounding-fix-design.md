---
title: "FIFO Integrity and Rounding Precision Fix"
created: "2026-05-29T04:15:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# FIFO Integrity and Rounding Precision Fix Design Document

## Problem Statement

The Finance Tracker system currently suffers from two critical data integrity issues:

1.  **FIFO Ghost Sells (Inconsistent Deletion Integrity)**:
    The CLI application interacts directly with the database layer for transaction deletions, bypassing the business logic in the service layer. When a 'Buy' transaction (a lot) is deleted, the system fails to check if any 'Sell' transactions have already been matched against that specific lot using the FIFO algorithm. This leaves 'orphan' sell entries with no corresponding buy data, corrupting the Realized P/L history and the 'partial_sold' state of the portfolio.

2.  **Rounding Drift (Premature Quantization)**:
    Rounding errors accumulate at a rate of ~40 IDR per 10,000 transactions. This occurs because:
    -   The FIFO logic in `SellService.execute_fifo_sell` quantizes (rounds) the IDR value for *each* lot slice individually before summing them.
    -   Reporting logic in `SQLiteIncomeRepository` and `MonthlyReportUseCase` uses Python's `sum()` on floating-point (REAL) database columns rather than using high-precision `Decimal` and deferred rounding at the final sum level.

## Requirements

### Functional Requirements

1.  **REQ-1 (Strict Deletion Blocking)**: The system MUST block the deletion of any investment lot if it has any associated sales (Status: `partial_sold` or `sold`). The user must first delete the associated Sell transactions before the Buy transaction can be removed.
2.  **REQ-2 (Service Layer Enforcement)**: All transaction mutations MUST route through the `InvestmentService` / `application` layer to ensure integrity checks are never bypassed.
3.  **REQ-3 (Precise Reporting)**: Transaction reports and summaries MUST use `Decimal` for all internal summations. Quantization to 0 decimal places (IDR) MUST only occur at the final report total level, not per transaction.
4.  **REQ-4 (FIFO Precision)**: The FIFO sell logic MUST sum the raw unrounded lot slice values first, and then apply a single quantization to the total sell value to minimize compound drift.

### Non-Functional Requirements

-   **Precision**: Maintain 100% precision for IDR values (integer parity at the total level).
-   **Performance**: High-volume report generation (10k+ rows) must complete in < 2 seconds despite using `Decimal`.
-   **Traceability**: All blocked deletions must provide a clear error message indicating *why* (e.g., "Cannot delete lot: associated sales found").

## Approach

### Selected Approach: Precision-First Refactor

1.  **Integrity Rerouting**:
    Refactor `apps/cli/investment_tracker/main.py` to use `InvestmentService.delete_investment`.
    -   *Rationale: Centralizes deletion logic in a single point of truth that already contains strict FIFO guards.*
    -   *Implementation*: Replace direct `repo.delete()` calls with `service.delete_investment()`.

2.  **Decimal Aggregation Pattern**:
    -   Update `SQLiteInvestmentRepository` and `SQLiteIncomeRepository` to perform aggregations using Python `Decimal` when loading rows.
    -   *Rationale: REAL columns in SQLite are floats. By converting to Decimal immediately upon read and using Decimal for the report total before rounding, we eliminate the floating-point drift.*

3.  **Deferred FIFO Quantization**:
    -   Modify `SellService.execute_fifo_sell` to keep a running Decimal sum of lot slice costs.
    -   *Rationale: Instead of `total += round(slice)`, we do `total = round(sum(slices))`. This fixes the 40 IDR drift.*

### Decision Matrix

| Criterion | Weight | Approach A (Pragmatic Patch) | Approach B (Selected: Precision Refactor) |
| :--- | :--- | :--- | :--- |
| **Integrity** | 40% | 3: Simple check in CLI main | 5: Enforced at Service Layer (REQ-2) |
| **Precision** | 40% | 2: Float math + extra rounding | 5: Decimal aggregation (REQ-3, REQ-4) |
| **Clean Code**| 20% | 3: Quick fix, adds debt | 5: Follows monorepo SSOT patterns |
| **Weighted Total** | | **2.6** | **5.0** |

## Agent Team

| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1     | coder    | No       | Service layer refactor, FIFO guard logic, Decimal integration |
| 2     | tester   | No       | Precision regression tests, FIFO deletion edge-case tests |

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
| :--- | :--- | :--- | :--- |
| **Performance Regression** | MEDIUM | LOW | Decimal is slower than float, but for 10k rows, Python handles it efficiently. We will benchmark the 10k report generation. |
| **Test Suite Breakage** | MEDIUM | MEDIUM | Existing tests might assert specific (imprecise) values. We must update `tests/unit/test_investment_logic.py` to match the corrected math. |
| **Database Type Mismatch** | LOW | LOW | SQLite `REAL` is float. We must ensure the `Decimal` conversion happens consistently in the Repository layer before any math. |

## Success Criteria

1.  **Verification of FIFO Guard**: Attempting to delete a partially sold lot via the CLI results in a `BlockingError` (or similar) and no data is removed.
2.  **Verification of Rounding**: A synthetic test with 10,000 transactions shows **zero drift** (Total sum == sum of raw values rounded once at the end).
3.  **Regression**: All existing investment and income tests pass.
