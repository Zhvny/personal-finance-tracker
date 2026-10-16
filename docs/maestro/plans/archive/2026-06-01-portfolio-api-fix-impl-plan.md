---
title: "Portfolio FX Integrity and API Dependency Fix Implementation Plan"
design_ref: "docs/maestro/plans/2026-06-01-portfolio-api-fix-design.md"
created: "2026-06-01T17:20:00Z"
status: "draft"
total_phases: 3
estimated_files: 5
task_complexity: "medium"
---

# Portfolio FX Integrity and API Dependency Fix Implementation Plan

## Plan Overview
- **Total phases**: 3
- **Agents involved**: `coder`, `tester`
- **Estimated effort**: Moderate refactor of core valuation logic and restoration of missing infrastructure.

## Dependency Graph
```
Phase 1: Foundation (PostgresFXRepository)
    |
Phase 2: Refactor (InvestmentService)
    |
Phase 3: Validation (API & Data Integrity)
```

## Execution Strategy
| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Restore missing repository |
| 2     | Phase 2 | Sequential | 1 | Core valuation logic |
| 3     | Phase 3 | Sequential | 1 | Integration testing |

---

## Phase 1: Infrastructure Foundation
### Objective
Implement `PostgresFXRepository` and update `FXService` to enable exchange rate persistence and satisfy API dependencies.

### Agent: `coder`
### Parallel: No

### Files to Create
- `packages/core/infrastructure/persistence/postgres_fx_repository.py`: Implements `IFXRepository` for PostgreSQL.

### Files to Modify
- `packages/core/infrastructure/external/fx_service.py`: Inject `PostgresFXRepository` and enable persistence calls.

### Validation
- Verify `packages/api/backend/routers/deps.py` can now import the repository without error.
- Run `python -c "from packages.core.infrastructure.persistence.postgres_fx_repository import PostgresFXRepository; print('Success')"`

---

## Phase 2: Valuation Logic Refactor
### Objective
Refactor `InvestmentService` to use current market prices and distinguish between Capital Gain and FX Gain.

### Agent: `coder`
### Parallel: No

### Files to Modify
- `packages/core/application/investment_service.py`: Update `get_active_investments` to calculate `curr_value` using live market data and live FX vs historical FX.
- `packages/core/utils/symbol_utils.py`: Ensure `GOLD` and `XAU` resolve to commodity futures (`GC=F`).

### Validation
- Unit test `InvestmentService.get_active_investments` with mocked market and FX data.

---

## Phase 3: Integration & Verification
### Objective
Confirm API server starts and validate financial accuracy of the new valuation logic.

### Agent: `tester`
### Parallel: No

### Files to Create
- `tests/integration/test_portfolio_valuation_integrity.py`: Integration test checking P/L for multi-year assets.

### Validation
- Start API server: `python packages/api/api_server.py` (verify no startup crash).
- Run integration tests.

---

## File Inventory
| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `packages/core/infrastructure/persistence/postgres_fx_repository.py` | 1 | DB persistence for FX |
| 2 | `packages/core/infrastructure/external/fx_service.py` | 1 | FX logic bridge |
| 3 | `packages/core/application/investment_service.py` | 2 | Core valuation refactor |
| 4 | `packages/core/utils/symbol_utils.py` | 2 | Gold normalization |
| 5 | `tests/integration/test_portfolio_valuation_integrity.py` | 3 | Verification |

## Risk Classification
| Phase | Risk | Rationale |
|-------|------|-----------|
| 1 | LOW | Standard repository implementation. |
| 2 | MEDIUM | Critical financial logic; requires careful handling of Decimals and FX dates. |
| 3 | LOW | Verification phase. |

## Execution Profile
```
Execution Profile:
- Total phases: 3
- Parallelizable phases: 0
- Sequential-only phases: 3
- Estimated parallel wall time: N/A
- Estimated sequential wall time: ~45 mins

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```
