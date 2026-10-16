---
title: "Income Error Fixes"
created: "2026-05-31T00:55:00.000Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Income Error Fixes Design Document

## Problem Statement

The `finance-tracker` project is currently experiencing three critical failures in the income tracking module:
1. **Persistence Failure**: The `SQLiteIncomeRepository` is incompatible with the `IncomeService` due to a method name mismatch (`get_summary_by_month` vs `get_monthly_summary`).
2. **UI Rendering Error**: The CLI application crashes when attempting to render panels with the invalid shorthand hex color `'#333'`, which is not supported by the `rich` library.
3. **Calculation Type Error**: A `TypeError` occurs during tax reporting because the calculation logic mixes `float` literals with `Decimal` data, preventing standard mathematical operations like division.

## Requirements

### Functional Requirements

1. **REQ-1**: `SQLiteIncomeRepository` must implement `get_monthly_summary` to satisfy the `IIncomeRepository` interface and `IncomeService` requirements.
2. **REQ-2**: All CLI styling must use 6-digit hex codes (e.g., `#333333`) to ensure compatibility with the `rich` library rendering.
3. **REQ-3**: The `IncomeCalculator` must use `Decimal` for all tax-related constants and return `Decimal` values.
4. **REQ-4**: `IncomeCLIView` must successfully calculate and display the tax ratio using consistent `Decimal` types.

### Non-Functional Requirements

1. **Precision**: Financial calculations must maintain decimal precision to avoid floating-point errors.
2. **Consistency**: Styling conventions must be standard across all CLI modules (Income and Expense).

### Constraints

- Must maintain compatibility with existing SQLite schemas.
- Must not introduce new dependencies.

## Approach

### Selected Approach

**Unified Domain Alignment & Decimal Precision**

1. **Repository**: Rename `get_summary_by_month` to `get_monthly_summary` in `SQLiteIncomeRepository`. This aligns the infrastructure layer with the domain contract.
2. **Styling**: Perform a surgical update of all `'#333'` instances to `'#333333'`.
3. **Calculation**: Refactor `IncomeCalculator` to use `Decimal` for tax rates (e.g., `Decimal('0.05')`) and thresholds. Update return types to `Decimal`.

### Decision Matrix (Type Safety)

| Criterion | Weight | Approach A (Full Decimal) | Approach B (Float Cast) |
| :--- | :--- | :--- | :--- |
| Precision | 40% | 5: Maintains exact decimal precision. | 2: Risks floating-point inaccuracies. |
| Code Quality | 30% | 5: Clean, consistent type usage. | 3: Adds "hacks" at call sites. |
| Effort | 30% | 3: Requires refactoring calculator. | 5: Single line cast in view. |
| **Weighted Total** | | **4.4** | **3.2** |

## Architecture

### Component Changes

- **packages/core/infrastructure/income_tracker/repository.py**: Rename `get_summary_by_month` to `get_monthly_summary`.
- **apps/cli/income_tracker/main.py**: Update border colors.
- **apps/cli/expense_tracker/main.py**: Update border colors.
- **apps/cli/income_tracker/core/calculator.py**: Convert constants and logic to use `Decimal`.
- **apps/cli/income_tracker/ui/cli_view.py**: Ensure clean `Decimal` division.

## Agent Team

| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1     | debugger | No       | Verified root causes and reproduction scripts |
| 2     | coder    | No       | Implementation of fixes |
| 3     | tester   | No       | Unit and integration test verification |

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Breaking Existing Reports | MEDIUM | LOW | Ensure data structure compatibility. |
| Calculation Regressions | MEDIUM | MEDIUM | Add unit tests for `IncomeCalculator`. |
| Styling Oversights | LOW | LOW | Use `grep_search` for shorthand hex codes. |

## Success Criteria

1. `SQLiteIncomeRepository.get_monthly_summary` is callable and returns correct data.
2. CLI starts without color parsing errors and renders panels correctly.
3. Tax estimates are calculated using `Decimal` and displayed correctly.
4. New or updated unit tests pass successfully.
