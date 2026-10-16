---
title: "Income Error Fixes Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-31-income-error-fixes-design.md"
created: "2026-05-31T01:10:00.000Z"
status: "completed"
total_phases: 3
estimated_files: 6
task_complexity: "medium"
---

# Income Error Fixes Implementation Plan

## Plan Overview

- **Total phases**: 3
- **Agents involved**: coder, tester
- **Estimated effort**: Moderate. Completed and verified.

## Dependency Graph

```
Phase 1: Investigation & Reproduction (COMPLETED)
    |
Phase 2: Core Implementation (COMPLETED)
    |
Phase 3: Verification & Testing (COMPLETED)
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Verified root causes |
| 2     | Phase 2 | Sequential | 1 | Applied fixes |
| 3     | Phase 3 | Sequential | 1 | Final validation complete |

---

## Phase 1: Investigation & Reproduction (COMPLETED)

### Objective
Empirically reproduce all three reported errors using scripts to ensure the fix can be verified.

### Agent: coder
### Parallel: No

### Files to Create

- `scripts/repro_income_errors.py` — Script to trigger the AttributeError, Color Error, and TypeError.

### Implementation Details
- Instantiate `SQLiteIncomeRepository` and call `get_monthly_summary`.
- Import `rich.panel` and attempt to render with `'#333'`.
- Call `IncomeCalculator.tax_estimate` with values that return 0.0 and perform division.

### Validation
- Run `python scripts/repro_income_errors.py` and confirm all three failures occur. (VERIFIED)

### Dependencies
- Blocked by: None
- Blocks: Phase 2

---

## Phase 2: Core Implementation (COMPLETED)

### Objective
Apply the fixes defined in the design document across the infrastructure, UI, and core layers.

### Agent: coder
### Parallel: No

### Files to Modify

- `packages/core/infrastructure/income_tracker/repository.py` — Rename `get_summary_by_month` to `get_monthly_summary`.
- `apps/cli/income_tracker/main.py` — Update color styles to `#333333`.
- `apps/cli/expense_tracker/main.py` — Update color styles to `#333333`.
- `apps/cli/income_tracker/core/calculator.py` — Refactor to use `Decimal` for tax rates and thresholds.
- `apps/cli/income_tracker/ui/cli_view.py` — Ensure `Decimal` division for tax ratios.

### Implementation Details
- Repository: Exact rename, ensuring no signature change.
- UI: Global search and replace for `'#333'`.
- Calculator: Use `from decimal import Decimal`. Replace `0.05` with `Decimal('0.05')`, `0.15` with `Decimal('0.15')`, etc. Update `PTKP` thresholds to `Decimal`.

### Validation
- Run the reproduction script `scripts/repro_income_errors.py` and confirm all checks pass. (VERIFIED)

### Dependencies
- Blocked by: Phase 1
- Blocks: Phase 3

---

## Phase 3: Verification & Testing (COMPLETED)

### Objective
Ensure full system integrity and add permanent unit tests for the refactored calculation logic.

### Agent: tester
### Parallel: No

### Files to Create
- `tests/unit/income_tracker/test_calculator_precision.py` — Unit tests for `IncomeCalculator` with various brackets.

### Files to Modify
- `tests/unit/infrastructure/test_sqlite_repo.py` — Update tests to use the new method name.

### Implementation Details
- Test brackets: Below PTKP, Bracket 1 (5%), Bracket 2 (15%), etc.
- Verify `Decimal` return type.

### Validation
- `python scripts/repro_income_errors.py` (Passed)
- `pytest tests/unit/income_tracker/test_calculator_precision.py` (Passed)

### Dependencies
- Blocked by: Phase 2
- Blocks: None

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `scripts/repro_income_errors.py` | 1 | Reproduction script |
| 2 | `packages/core/infrastructure/income_tracker/repository.py` | 2 | Repository fix |
| 3 | `apps/cli/income_tracker/main.py` | 2 | UI color fix |
| 4 | `apps/cli/expense_tracker/main.py` | 2 | UI color fix |
| 5 | `apps/cli/income_tracker/core/calculator.py` | 2 | Calculation type safety |
| 6 | `apps/cli/income_tracker/ui/cli_view.py` | 2 | UI type safety |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1 | LOW | Non-destructive investigation. |
| 2 | MEDIUM | Refactoring core calculation logic requires precision. |
| 3 | LOW | Verification only. |

## Execution Profile

```
Execution Profile:
- Total phases: 3
- Parallelizable phases: 0
- Sequential-only phases: 3
- Estimated parallel wall time: N/A
- Estimated sequential wall time: 10-15 mins

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
