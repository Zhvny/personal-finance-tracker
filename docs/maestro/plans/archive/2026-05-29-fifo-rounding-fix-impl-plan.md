---
title: "FIFO Integrity and Rounding Precision Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-29-fifo-rounding-fix-design.md"
created: "2026-05-29T04:30:00Z"
status: "draft"
total_phases: 3
estimated_files: 8
task_complexity: "medium"
---

# FIFO Integrity and Rounding Precision Implementation Plan

## Plan Overview

- **Total phases**: 3
- **Agents involved**: `coder`, `tester`
- **Estimated effort**: Medium. Focuses on centralizing business logic for deletions and migrating financial math from `float` to `Decimal` across the Application and Infrastructure layers.

## Dependency Graph

```
Phase 1 (Integrity) 
      |
Phase 2 (Precision Repo & FIFO)
      |
Phase 3 (Validation & Stress Test)
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Foundation: Integrity Rerouting |
| 2     | Phase 2 | Sequential | 1 | Core: Decimal Persistence & FIFO |
| 3     | Phase 3 | Sequential | 1 | Quality: Stress & Regression |

---

## Phase 1: Integrity Enforcement & Service Rerouting

### Objective
Block "Ghost Sells" by ensuring all deletions route through the Service Layer with strict referential integrity checks.

### Agent: coder
### Parallel: No

### Files to Modify

- `apps/cli/investment_tracker/main.py` — Replace direct `SQLiteInvestmentRepository.delete` calls in `edit_delete` with `InvestmentService.delete_investment`.
- `packages/core/application/investment_service.py` — Implement REQ-1 in `delete_investment`. Check lot status (`partial_sold`, `sold`) and raise `IntegrityError` if sales exist.

### Implementation Details

- **Integrity Check**:
  ```python
  def delete_investment(self, investment_id: str):
      investment = self.repo.get_by_id(investment_id)
      if investment.status in [Status.PARTIAL_SOLD, Status.SOLD]:
          raise IntegrityError(f"Cannot delete investment {investment_id}: associated sales found.")
      self.repo.delete(investment_id)
  ```
- **Error Handling**: Update `main.py` to catch `IntegrityError` and display a user-friendly message.

### Validation

- `pytest tests/unit/test_investment_logic.py` (Add new tests for deletion blocking).
- `python tests/run_exhaustive_qa.py` (Verify manual deletion flow in CLI).

### Dependencies

- Blocked by: None
- Blocks: Phase 2, Phase 3

---

## Phase 2: Precision Repository & FIFO Fix

### Objective
Eliminate Rounding Drift by migrating persistence to `Decimal` and deferring quantization in the FIFO algorithm.

### Agent: coder
### Parallel: No

### Files to Modify

- `packages/core/infrastructure/investment_tracker/sqlite_repository.py` — Ensure `REAL` columns are mapped to `Decimal` using `decimal.Decimal(str(row['value']))` to avoid float contamination.
- `packages/core/infrastructure/income_tracker/repository.py` — Update aggregation queries to use Python-side `Decimal` summation.
- `packages/core/infrastructure/income_tracker/models.py` — Change `Income.amount` type from `float` to `Decimal`.
- `apps/cli/investment_tracker/services/sell_service.py` — Refactor `execute_fifo_sell` to sum lot slice costs as `Decimal` before a single quantization at the end.

### Implementation Details

- **Deferred Quantization Pattern**:
  ```python
  # Old: total += round(slice_value)
  # New:
  total_raw = Decimal('0')
  for slice in slices:
      total_raw += slice.cost_basis
  quantized_total = total_raw.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
  ```
- **Repository Mapping**: Update `_map_row_to_investment` and `_map_row_to_income` to use `Decimal`.

### Validation

- `pytest tests/unit/test_financial_math_invariants.py` (Existing tests for drift).
- `pytest tests/unit/test_income_logic.py`.

### Dependencies

- Blocked by: Phase 1
- Blocks: Phase 3

---

## Phase 3: Comprehensive Validation & Stress Testing

### Objective
Verify the fixes under high volume and ensure no regressions in financial reporting.

### Agent: tester
### Parallel: No

### Files to Create

- `tests/stability/test_precision_volume.py` — New test case generating 10,000 transactions and asserting zero drift between raw inputs and final repository totals.

### Files to Modify

- `tests/unit/test_financial_math_invariants.py` — Refine assertions to be exact (integer parity) rather than using `pytest.approx`.

### Implementation Details

- **Stress Test**:
  - Generate 10,000 'Buy' transactions with prime-number prices (to maximize float entropy).
  - Execute a single large 'Sell' that consumes all 10,000 lots.
  - Assert `total_realized_pl` matches the exact IDR calculation.

### Validation

- `pytest tests/stability/test_precision_volume.py`
- `python scripts/benchmark_latency.py` (Verify Decimal performance impact).

### Dependencies

- Blocked by: Phase 2
- Blocks: None

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `apps/cli/investment_tracker/main.py` | 1 | Route deletions to Service Layer |
| 2 | `packages/core/application/investment_service.py` | 1 | Implement deletion blocking logic |
| 3 | `packages/core/infrastructure/investment_tracker/sqlite_repository.py` | 2 | Decimal persistence mapping |
| 4 | `packages/core/infrastructure/income_tracker/repository.py` | 2 | Decimal aggregation logic |
| 5 | `packages/core/infrastructure/income_tracker/models.py` | 2 | Income model precision |
| 6 | `apps/cli/investment_tracker/services/sell_service.py` | 2 | Deferred FIFO quantization |
| 7 | `tests/stability/test_precision_volume.py` | 3 | 10k transaction stress test |
| 8 | `tests/unit/test_financial_math_invariants.py` | 3 | Regression & Invariant verification |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1     | LOW  | Logic is straightforward; primary risk is missing a CLI path to deletion. |
| 2     | MEDIUM | Repository migrations in SQLite can be tricky with types; needs careful mapping. |
| 3     | LOW  | Pure validation phase. |

## Execution Profile

```
Execution Profile:
- Total phases: 3
- Parallelizable phases: 0
- Sequential-only phases: 3
- Estimated parallel wall time: N/A
- Estimated sequential wall time: ~45 mins (including 10k stress test run)

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
