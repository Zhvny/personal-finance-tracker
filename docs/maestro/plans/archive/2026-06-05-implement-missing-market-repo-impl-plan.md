---
title: "Implement Missing PostgresMarketDataRepository Implementation Plan"
design_ref: "docs/maestro/plans/2026-06-05-implement-missing-market-repo-design.md"
created: "2026-06-05T02:20:00Z"
status: "approved"
total_phases: 3
estimated_files: 3
task_complexity: "medium"
---

# Implement Missing PostgresMarketDataRepository Implementation Plan

## Plan Overview
- **Total phases**: 3
- **Agents involved**: `coder`, `tester`
- **Estimated effort**: Implementation of a missing repository and resolving interface mismatches.

## Dependency Graph
```
[Phase 1: Implement Repo]
       |
[Phase 2: Fix Interface Mismatch]
       |
[Phase 3: Integration Verification]
```

## Execution Strategy
| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Foundation |
| 2     | Phase 2 | Sequential | 1 | Interface alignment |
| 3     | Phase 3 | Sequential | 1 | Quality Gate |

## Phase 1: Implement PostgresMarketDataRepository
### Objective
Create the missing `PostgresMarketDataRepository` class to handle latest price persistence.

### Agent: coder
### Parallel: No

### Files to Create
- `packages/core/infrastructure/persistence/postgres_market_data_repository.py` — Implements `IMarketDataRepository` using `market.latest_prices` table.

### Implementation Details
- Use `DatabaseManager` for SQL execution.
- Implement UPSERT logic: `INSERT ... ON CONFLICT (ticker) DO UPDATE`.
- Map `MarketData` model to table columns: `ticker`, `price`, `timestamp`, `change_pct`, `volume`, `metadata`.

### Validation
- `python -c "from packages.core.infrastructure.persistence.postgres_market_data_repository import PostgresMarketDataRepository; print('Import Success')"`

### Dependencies
- Blocked by: None
- Blocks: Phase 2

## Phase 2: Fix Interface Mismatch
### Objective
Add `save_ohlcv` to `PostgresOHLCVRepository` and ensure `MarketDataService` compatibility.

### Agent: coder
### Parallel: No

### Files to Modify
- `packages/core/infrastructure/persistence/postgres_ohlcv_repository.py` — Add `save_ohlcv` method.

### Implementation Details
- `save_ohlcv` should persist individual data points to `market.ohlcv_cache` or a suitable historical table.
- Since the design doc for June 1st was incomplete, I'll implement `save_ohlcv` to match the expected signature in `MarketDataService`.

### Validation
- Check `MarketDataService` initialization in `market_scheduler.py`.

### Dependencies
- Blocked by: Phase 1
- Blocks: Phase 3

## Phase 3: Integration Verification
### Objective
Verify that the `api_server` starts and the scheduler fetches data without errors.

### Agent: tester
### Parallel: No

### Validation
- Run `python packages/api/api_server.py`.
- Monitor logs for "Market Data Scheduler started" and successful price updates.

### Dependencies
- Blocked by: Phase 2
- Blocks: None

## File Inventory
| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `packages/core/infrastructure/persistence/postgres_market_data_repository.py` | 1 | Core repository implementation |
| 2 | `packages/core/infrastructure/persistence/postgres_ohlcv_repository.py` | 2 | Interface fix |

## Risk Classification
| Phase | Risk | Rationale |
|-------|------|-----------|
| 1     | LOW | Standard repository implementation. |
| 2     | MEDIUM | Mismatch between service expectations and repository capabilities. |
| 3     | LOW | Final verification. |
