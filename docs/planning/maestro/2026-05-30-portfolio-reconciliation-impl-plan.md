---
title: "Portfolio Data Reconciliation Implementation Plan"
design_ref: "docs/maestro/plans/2026-05-30-portfolio-reconciliation-design.md"
created: "2026-05-30T10:30:00Z"
status: "draft"
total_phases: 2
estimated_files: 1
task_complexity: "medium"
---

# Portfolio Data Reconciliation Implementation Plan

## Plan Overview

- **Total phases**: 2
- **Agents involved**: coder, tester
- **Estimated effort**: MEDIUM. Targeted reconciliation script using existing service layers.

## Dependency Graph

```
Phase 1: Reconciliation Script (coder)
    |
    v
Phase 2: Data Verification (tester)
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Implementation |
| 2     | Phase 2 | Sequential | 1 | Verification |

## Phase 1: Portfolio Reconciliation Script

### Objective
Implement a targeted Python script to reconcile specific portfolio discrepancies (AAPL, AMZN, NVDA, GOLD, GOOG) in the PostgreSQL `personal` schema using the application service layer.

### Agent: coder
### Parallel: No

### Files to Create

- `scripts/tools/reconcile_portfolio_20260530.py` — Script to execute the reconciliation logic using `InvestmentService`, `FXService`, and `DatabaseManager`.

### Files to Modify
None.

### Implementation Details

- **Service Injection**: Instantiate `InvestmentService` with `PostgresRepository`.
- **Schema Context**: Use `DatabaseManager` to ensure `SET search_path TO personal`.
- **FX Rates**: Call `FXService.get_rate_at()` for trade dates (2026-05-28 and 2026-05-30) to ensure accurate P/L calculation in IDR.
- **Transactions**:
    1. Sell AAPL (Lot 8): 0.12408647 shares at $191.29 (2026-05-30).
    2. Sell AMZN (Lots 7, 9, 16): 1.27926373 shares at $181.28 (2026-05-30).
    3. Sell NVDA (Lots 4, 6): 0.80683736 shares at $1,064.69 (2026-05-28).
    4. Buy GOOG: 0.3941432 shares at $177.60 (2026-05-28).
    5. Sell GOLD (Lot 18): 0.8g at ~$146.70/g (2026-05-30).
- **Error Handling**: Wrap each transaction in a try-except block; report successes/failures to console.

### Validation

- `python scripts/tools/reconcile_portfolio_20260530.py --dry-run` (if implemented)
- `python scripts/tools/reconcile_portfolio_20260530.py`
- Check logs for "Success" messages and correct P/L amounts.

### Dependencies

- Blocked by: None
- Blocks: Phase 2

---

## Phase 2: Data Verification

### Objective
Verify that the PostgreSQL `personal` schema correctly reflects the current state of the portfolio after reconciliation.

### Agent: tester
### Parallel: No

### Files to Create
None.

### Files to Modify
None.

### Implementation Details

- **Verification Strategy**:
    - Run `scripts/verify_holdings.py` to check for quantity discrepancies.
    - Run `scripts/verify_lot_tracking.py` to ensure FIFO integrity.
    - Run `scripts/check_postgres_data.py` to inspect the `sell_transactions` table for the new reconciliation entries.
- **Success Criteria**:
    - AAPL, AMZN, NVDA (targeted lots) show 0 remaining quantity and 'sold' status.
    - GOOG shows 0.3941432 shares in active holdings.
    - GOLD Lot 18 shows 9.2g remaining.
    - Realized P/L matches expected values from sell prices.

### Validation

- Exit code 0 from all verification scripts.
- Visual confirmation of `sell_transactions` for reconciliation timestamps (2026-05-30).

### Dependencies

- Blocked by: Phase 1
- Blocks: None

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `scripts/tools/reconcile_portfolio_20260530.py` | 1 | Primary reconciliation logic |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1     | MEDIUM | Direct mutation of financial data. Mitigation: Service-layer validation and dry-run check. |
| 2     | LOW | Read-only verification. |

## Execution Profile

```
Execution Profile:
- Total phases: 2
- Parallelizable phases: 0
- Sequential-only phases: 2
- Estimated parallel wall time: N/A
- Estimated sequential wall time: 10-15 minutes

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
