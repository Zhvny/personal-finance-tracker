---
title: "Fix Missing Data in VIEW_PORTFOLIO"
created: "2026-05-31T00:20:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Fix Missing Data in VIEW_PORTFOLIO Design Document

## Problem Statement

The `VIEW_PORTFOLIO` command currently fails to display critical data (QTY, BUY_PRICE, CURR_VAL, TOTAL_P/L, and P/L %) if live price fetching fails and no historical price snapshots exist. This happens because `_fetch_prices` returns `None`, causing the UI to default to "—" for all metrics. Additionally, the `buy_price_idr` field is often missing in the domain model due to inconsistent initialization in the repository mapping, leading to broken cost-basis calculations.

## Requirements

### Functional Requirements

1. **REQ-1**: `VIEW_PORTFOLIO` must display QTY and BUY_PRICE for all active holdings, even if current market price is unavailable.
2. **REQ-2**: `buy_price_idr` must be reliably populated during repository retrieval.
3. **REQ-3**: The UI must fallback to historical snapshots or cost-basis for "Current Value" display when live data is missing.

### Non-Functional Requirements

1. **Robustness**: The application must not crash or display empty tables due to network or API failures.
2. **Consistency**: Data displayed in the CLI must align with the underlying database records.

## Approach

### Selected Approach: Dual-Layer Data Recovery

**1. Repository Layer Enhancement**
Update `SQLiteInvestmentRepository._map_row_to_investment` to calculate `buy_price_idr` at runtime if it's missing. This ensures the domain model is always complete without requiring a database migration.
*Rationale: Decouples UI logic from raw DB state and fixes cost-basis calculations globally.*

**2. Application Layer Refactor**
Refactor `PortfolioApp._fetch_prices` to always return a valid price dictionary. 
- If live fetch fails and snapshot exists: Use snapshot data (already implemented but needs verification).
- If live fetch fails and NO snapshot exists: Use `buy_price_idr` as `current_price_idr` and mark as `stale`.
*Rationale: Ensures the UI always has numeric data to render columns, even if profit is shown as zero.*

### Decision Matrix

| Criterion | Weight | Selected Approach | Alt: UI-Only Patches |
|-----------|--------|-------------------|----------------------|
| Data Consistency | 40% | 5: Ensures SSOT in model | 3: Fragmented logic |
| Robustness | 30% | 5: Handles all failure modes | 4: UI-only fallback |
| Maintenance | 30% | 4: Small repo + app changes | 5: Single file change |
| **Weighted Total** | | **4.7** | **3.9** |

## Architecture

### Data Flow
`DB` -> `SQLiteInvestmentRepository` (maps row + calculates IDR cost) -> `PortfolioApp` (fetches prices + applies fallbacks) -> `CLIView` (renders table).

### Key Interfaces
```python
# Updated return contract for _fetch_prices
{
    inv_id: {
        "usd": float,
        "idr": float,
        "buy_price_idr": float,
        "current_price_idr": float,
        "stale": bool,
        "last_updated": datetime
    }
}
```

## Agent Team

| Phase | Agent | Parallel | Deliverables |
|-------|-------|----------|--------------|
| 1     | coder | No       | Updated repository mapping and price fetching logic |
| 2     | tester| No       | Verification of portfolio display under fetch failure |

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Fetch logic complexity | LOW | MEDIUM | Keep dictionary structure simple and documented |
| Performance hit (FX calls) | MEDIUM | LOW | Cache FX rates (already implemented) |

## Success Criteria

1. `VIEW_PORTFOLIO` displays QTY, BUY_PRICE, and CURR_VAL for all active stocks.
2. If network is down, metrics show last known values or cost-basis instead of "—".
3. `buy_price_idr` is correctly initialized for both IDR and USD investments.
