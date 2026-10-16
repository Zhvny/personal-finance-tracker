---
title: "Fix API Crash and CLI Syntax Error"
created: "2026-06-01T15:25:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Fix API Crash and CLI Syntax Error Design Document

## Problem Statement
The Finance Tracker ecosystem is currently experiencing two critical failures:
1. **API Crash (Blocking)**: The `api_server` cannot start because `MarketScheduler` depends on `PostgresMarketDataRepository`, which is missing from the codebase.
2. **CLI Regression**: The "Expense" module in the CLI fails to launch due to a syntax error in `apps/cli/expense_tracker/main.py:120`.

## Approach
### Selected Approach
**Restoration and Surgical Fix**
- Implement `PostgresMarketDataRepository` in `packages/core/infrastructure/persistence/` implementing `IMarketDataRepository`.
- Fix the merged statements in `apps/cli/expense_tracker/main.py:120`.

### Alternatives Considered
- **Mock Repository**: Allow API startup but leave market sync broken. Rejected for functionality.
- **Merge Schema**: Use OHLCV cache for all market data. Rejected for domain purity.

## Risk Assessment
| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Schema Mismatch | MEDIUM | MEDIUM | Validate Pydantic models against query results. |
| Import Cycles | LOW | LOW | Use strict absolute imports. |
| Regression | LOW | LOW | Verify module launch post-fix. |
