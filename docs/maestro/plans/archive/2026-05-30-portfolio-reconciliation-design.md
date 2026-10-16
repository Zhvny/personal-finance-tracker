---
title: "Portfolio Data Reconciliation"
created: "2026-05-30T00:00:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Portfolio Data Reconciliation Design Document

## Problem Statement
The user's current portfolio data in the `personal` schema is outdated and contains inaccuracies:
1.  **Sold Assets Still Active**: NVDA, AAPL, AMZN, and a portion of GOLD (0.8g) have been sold but are still listed as active holdings.
2.  **Missing Purchases**: A recent purchase of GOOG is not correctly reflected (currently exists as a zero-quantity entry).
3.  **Data Noise**: Several 'zero-quantity' lots for various tickers (BBS, BGS, MSFT, etc.) were created as artifacts and need to be acknowledged but kept.
4.  **Evidence**: Transaction details are provided via OCR receipts in `tests/ocr_iamge_input_test`.

## Requirements

### Functional Requirements
1.  **REQ-1 (AAPL Sell)**: Record the sale of 0.12408647 AAPL shares at $191.29 (Date: 2026-05-30). Update status to 'sold'.
2.  **REQ-2 (AMZN Sell)**: Record the sale of all AMZN holdings (Lots: 7, 9, 16) totaling 1.27926373 shares at $181.28 (Date: 2026-05-30). Update status to 'sold'.
3.  **REQ-3 (NVDA Sell)**: Record the sale of NVDA holdings (Lots: 4, 6) totaling 0.80683736 shares at $1,064.69 (Date: 2026-05-28). Update status to 'sold'.
4.  **REQ-4 (GOOG Buy)**: Record the purchase of 0.3941432 GOOG shares at $177.60 (Date: 2026-05-28).
5.  **REQ-5 (GOLD Partial Sell)**: Record the sale of 0.8g GOLD from Lot 18. Use price of ~$146.70/g (Date: 2026-05-30). Update remaining quantity to 9.2g.
6.  **REQ-6 (Preserve Noise)**: Do not delete zero-quantity lots (BBS, BGS, etc.); these are to be kept for historical/PL context.

### Non-Functional Requirements
-   **Data Integrity**: Use existing `InvestmentService` or equivalent logic to ensure FIFO rules and correct P/L calculations (converted to IDR).
-   **Auditability**: Ensure all changes are reflected in the `audit_log`.

### Constraints
-   Transactions must be recorded in the `personal` schema of the PostgreSQL database.

## Approach

### Selected Approach
**Service-Level Reconciliation Script**
A custom Python script will be created to perform the following operations sequentially within the `personal` schema:
1.  **Sell AAPL**: Call `sell_investment` for Lot 8.
2.  **Sell AMZN**: Call `sell_investment` for Lots 7, 9, 16.
3.  **Sell NVDA**: Call `sell_investment` for Lots 4, 6.
4.  **Buy GOOG**: Call `add_investment` for 0.3941432 shares.
5.  **Sell GOLD**: Call `sell_investment` for 0.8g from Lot 18.

*Rationale*: Leveraging the existing service layer ensures P/L accuracy and maintains lifecycle status.

### Alternatives Considered
-   **Manual SQL Patching**: Directly updating tables. *Rejected*: High risk of integrity violations.
-   **CSV Import**: Batch processing. *Rejected*: Unnecessary for this scale.

### Decision Matrix
| Criterion | Weight | Service-Layer | Manual SQL |
|-----------|--------|---------------|------------|
| Accuracy  | 50%    | 5: Native P/L | 2: Risk    |
| Integrity | 30%    | 5: Enforced   | 1: Bypassed|
| Speed     | 20%    | 4: Scripted   | 5: Instant |
| **Total** |        | **4.8**       | **2.3**    |

## Architecture
The script will use `packages.core.application.investment_service.InvestmentService` backed by `packages.core.infrastructure.investment_tracker.repository.PostgresRepository`.

## Agent Team
| Phase | Agent | Parallel | Deliverables |
|-------|-------|----------|--------------|
| 1     | coder | No       | Reconciliation Script |
| 2     | tester| No       | Verification Report |

## Risk Assessment
| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| FX Discrepancy | MEDIUM | LOW | Use `FXService` for trade-date rates. |
| Schema Context | LOW | LOW | Explicit `SET search_path TO personal`. |

## Success Criteria
1.  Remaining quantities for sold lots set to 0.
2.  New GOOG lot correctly recorded.
3.  Realized P/L entries created in `sell_transactions`.
4.  Portfolio status reflects current reality.
