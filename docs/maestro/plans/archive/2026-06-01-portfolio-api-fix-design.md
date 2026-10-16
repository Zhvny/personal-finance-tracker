---
title: "Portfolio FX Integrity and API Dependency Fix"
created: "2026-06-01T17:15:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Portfolio FX Integrity and API Dependency Fix Design Document

## Problem Statement

The system currently suffers from two distinct but critical failures:
1. **API Crash**: Missing `PostgresFXRepository` causes a `ModuleNotFoundError` in the API server.
2. **Valuation Inaccuracy**: Portfolio "Current Value" calculations are often stale or misleading (0% P/L fallback) because they fail to properly integrate current market prices with historical vs. live FX rates, particularly for long-term holdings and commodities like Gold.

## Requirements

### Functional Requirements
- **REQ-1**: Implement `PostgresFXRepository` in `packages.core` to resolve the API crash and provide persistence for exchange rates.
- **REQ-2**: Refactor `InvestmentService` to calculate valuations using a "Strict Value" protocol: Current Price (Market) × Current FX (Live) vs. Buy Price (Original) × Buy FX (Historical).
- **REQ-3**: Distinguish between Capital Gain (price movement in asset currency) and FX Gain (currency fluctuation impact).
- **REQ-4**: Standardize Gold pricing to use futures-based market data normalized to per-gram IDR.

### Non-Functional Requirements
- **NFR-1**: Data Transparency: Flag stale prices in the UI instead of silent fallbacks to buy price.
- **NFR-2**: Persistence: Cache fetched FX and Market data to minimize API rate limit issues.

## Approach

### Selected Approach: Robust Integration
We will implement the missing infrastructure and refactor the core valuation logic to align with the monorepo's Clean Architecture standards.

### Decision Matrix

| Criterion | Weight | Pragmatic Patch | Robust Integration |
|-----------|--------|-----------------|--------------------|
| Data Accuracy | 40% | 3 (Adequate) | 5 (Precise breakdown) |
| System Stability | 30% | 4 (Low risk) | 4 (Fixes API crash) |
| Maintainability | 20% | 3 (Increases debt) | 5 (Aligned with arch) |
| Speed of Impl | 10% | 5 (Fast) | 3 (Complex refactor) |
| **Weighted Total** | | **3.7** | **4.5** |

## Architecture

### Component Diagram
```
[API Server] -> [InvestmentService] -> [PostgresInvestmentRepository]
                      |
                      v
                [FXService] -> [PostgresFXRepository]
                      |
                      v
                [YFinanceFetcher]
```

### Data Flow
1. API/CLI requests active investments.
2. `InvestmentService` fetches raw lots from Repository.
3. For each lot, it fetches:
   - Historical FX (Buy Date) from `FXService`.
   - Current Price (USD/IDR) from `YFinanceFetcher`.
   - Current FX (Live) from `FXService`.
4. Logic calculates `curr_value_idr = current_price * current_fx * quantity`.
5. P/L is decomposed into `cap_gain` and `fx_gain`.

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Price API Rate Limits | MEDIUM | MEDIUM | Caching in `FXService` and `YFinanceFetcher`. |
| Missing Historical FX | LOW | MEDIUM | Use closest available date; fallback to 16k. |
| DB Schema Mismatch | MEDIUM | LOW | Pre-validation of Postgres tables. |

## Success Criteria
1. API Server starts without `ModuleNotFoundError`.
2. Portfolio view shows non-zero P/L for long-term assets when market prices have changed.
3. Gold valuations match current per-gram IDR market rates.
