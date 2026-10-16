---
title: "Implement Missing PostgresMarketDataRepository"
created: "2026-06-05T02:15:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "standard"
task_complexity: "medium"
---

# Implement Missing PostgresMarketDataRepository Design Document

## Problem Statement
The `api_server` and `MarketScheduler` cannot start because the `PostgresMarketDataRepository` module is missing. This repository is required to persist and retrieve real-time market data in the PostgreSQL database.

## Requirements
### Functional Requirements
1. **REQ-1**: Implement `IMarketDataRepository` interface methods.
2. **REQ-2**: Persist market data to `market.latest_prices` table.
3. **REQ-3**: Support UPSERT logic (Update if exists, Insert if not) based on ticker symbol.

### Non-Functional Requirements
1. **PERF-1**: Use `DatabaseManager` connection pooling for efficiency.
2. **MAINT-1**: Follow clean architecture patterns by isolating infrastructure logic.

## Approach
### Selected Approach
**PostgreSQL Repository Implementation**
- Create `packages/core/infrastructure/persistence/postgres_market_data_repository.py`.
- Implement `save`, `get_latest`, and `get_history`.
- Map `MarketData` model fields to `market.latest_prices` columns.

### Alternatives Considered
- **SQLite Fallback**: Use local SQLite for market data. Rejected to maintain system-wide synchronization.
- **OHLCV Overload**: Use OHLCV table for latest prices. Rejected to avoid bloat and maintain schema clarity.

## Architecture
### Component Diagram
```
[MarketScheduler] -> [MarketDataService] -> [PostgresMarketDataRepository] -> [PostgreSQL (market.latest_prices)]
```

### Data Flow
1. `MarketDataService` fetches price via `YFinanceFetcher`.
2. `MarketDataService` passes `MarketData` object to `PostgresMarketDataRepository.save()`.
3. Repository executes UPSERT SQL via `DatabaseManager`.

## Agent Team
| Phase | Agent(s) | Parallel | Deliverables |
|-------|----------|----------|--------------|
| 1     | coder    | No       | `postgres_market_data_repository.py` |
| 2     | tester   | No       | Integration verification |

## Risk Assessment
| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Schema Mismatch | MEDIUM | MEDIUM | Explicit mapping of Pydantic fields to SQL columns. |
| DB Connectivity | LOW | LOW | Ensure `DatabaseManager` is initialized before use. |

## Success Criteria
1. `api_server` starts without `ModuleNotFoundError`.
2. `MarketScheduler` successfully saves fetched prices to the database.
