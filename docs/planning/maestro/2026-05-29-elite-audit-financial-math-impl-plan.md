Last Updated: 29-05-2026 (14:30)

---
title: "Elite Audit: Financial Math Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-29-elite-audit-financial-math-design.md"
created: "2026-05-29T20:00:00Z"
status: "approved"
total_phases: 4
estimated_files: 10
task_complexity: "complex"
---

# Elite Audit: Financial Math Implementation Plan

## Plan Overview

- **Total phases**: 4
- **Agents involved**: `coder`, `refactor`, `tester`
- **Estimated effort**: Complex refactor across models, repositories, and calculation logic.

## Dependency Graph

```
Phase 1: Foundation (Models & Migration)
    |
Phase 2: Repository Update (Decimal Enforcement)
    |
Phase 3: Service Logic (FIFO Integrity & Rounding)
    |
Phase 4: Validation & Final Audit
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Schema & Models |
| 2     | Phase 2 | Sequential | 1 | Repository layer |
| 3     | Phase 3 | Sequential | 1 | Calculation logic |
| 4     | Phase 4 | Sequential | 1 | Final verification |

## Phase 1: Foundation (Models & Migration)

### Objective
Update core domain models to use `Decimal` and prepare the database schema with constraints.

### Agent: `coder`
### Parallel: No

### Files to Modify
- `packages/core/domain/models/investment.py`: Change `float` to `Decimal` for `quantity`, `buy_price`, `buy_price_idr`, `remaining_quantity`, etc.
- `scripts/setup_postgres.py`: Add `CHECK (remaining_quantity >= 0)` and `CHECK (buy_price >= 0)` to `investment.investments`.

### Validation
- Run `python scripts/setup_postgres.py` to ensure schema updates are valid.
- Run `pydantic` model validation tests.

## Phase 2: Repository Update (Decimal Enforcement)

### Objective
Enforce `Decimal` usage in all repository implementations.

### Agent: `coder`
### Parallel: No

### Files to Modify
- `packages/core/infrastructure/investment_tracker/repository.py`
- `packages/core/infrastructure/investment_tracker/sqlite_repository.py`
- `packages/core/infrastructure/persistence/postgres_investment_repository.py`

### Implementation Details
- Ensure all values fetched from SQL (which might be returned as `float` or `str`) are cast to `Decimal`.
- Ensure values passed to SQL are handled correctly by the database drivers.

### Validation
- Test CRUD operations with `Decimal` values.
- Verify that `0.1 + 0.2` stored and retrieved remains exactly `0.3`.

## Phase 3: Service Logic (FIFO Integrity & Rounding)

### Objective
Update calculation services to use `Decimal` and implement recursive FIFO integrity checks.

### Agent: `refactor`
### Parallel: No

### Files to Modify
- `apps/cli/investment_tracker/services/sell_service.py`: Update to use `Decimal`.
- `packages/core/application/investment_service.py`: Update to use `Decimal`.

### Implementation Details
- Implement `FIFOIntegrityCheck` that runs after lot deletion.
- Update `SellService.execute_fifo_sell` to use `Decimal` for all math.
- Add total-level rounding using `quantize(Decimal('0.01'))`.

### Validation
- Unit tests for `SellService` with `Decimal`.
- Reproduction test for "Ghost Sells" after lot deletion.

## Phase 4: Validation & Final Audit

### Objective
Exhaustive testing of financial invariants.

### Agent: `tester`
### Parallel: No

### Files to Create
- `tests/unit/test_financial_math_invariants.py`: New test suite for the fixed vectors.

### Validation
- Re-run all 10 vectors from `AUDIT_FINANCE_REPORT_20260525.md`.
- Verify no negative cost basis can be created.

---\\n
## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `packages/core/domain/models/investment.py` | 1 | Domain model update |
| 2 | `scripts/setup_postgres.py` | 1 | Database schema update |
| 3 | `packages/core/infrastructure/investment_tracker/repository.py` | 2 | Repo implementation |
| 4 | `apps/cli/investment_tracker/services/sell_service.py` | 3 | FIFO logic update |
| 5 | `tests/unit/test_financial_math_invariants.py` | 4 | Verification |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1     | MEDIUM | Schema changes can break existing data if not handled carefully. |
| 2     | LOW | Purely typing and casting changes. |
| 3     | HIGH | Core financial logic changes; potential for breakage in sell execution. |
| 4     | LOW | Verification phase. |

## Execution Profile

```
Execution Profile:
- Total phases: 4
- Parallelizable phases: 0
- Sequential-only phases: 4
- Estimated parallel wall time: 4 hours
- Estimated sequential wall time: 4 hours

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
