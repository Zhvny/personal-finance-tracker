Last Updated: 29-05-2026 (14:30)

# 2025-05-25 Merge Resolution Design

## Context
Resolving conflicts between `qa-testing-cli` and `master`. 

## Key Decisions

### 1. Structure Flattening
Master branch has flattened `packages/core/` into `application`, `domain`, and `infrastructure` folders directly. `qa-testing-cli` uses a `src/` subfolder.
- **Action**: Update all imports to omit `src/`. Ensure files are in the flattened locations.

### 2. SQLite First
Master is SQLite-only for the CLI.
- **Action**: Revert any Postgres/DatabaseManager initialization or repository overrides found in `qa-testing-cli`.

### 3. FIFO Sell Integration
`qa-testing-cli` introduced `execute_fifo_sell` in `SellService` and the corresponding UI in `PortfolioApp.sell_asset`.
- **Action**: Merge these features into the master files while fixing the imports to match the flattened structure.

### 4. Scheduler PID Locking
`qa-testing-cli` added PID locking to the scheduler.
- **Action**: Merge the PID locking logic into the Master `scheduler.py` which currently uses central logging.

## File-Specific Resolution Strategy

- **apps/cli/main.py**: Keep Master's `SQLite` repositories and imports. Ensure `MaintenanceService` and `BusinessReportService` imports are flattened.
- **apps/cli/investment_tracker/main.py**: Port the `sell_asset` FIFO logic. Keep Master's `InvestmentRepository` (SQLite). Fix imports.
- **apps/cli/investment_tracker/services/sell_service.py**: Keep `execute_fifo_sell`. Fix `Investment` imports to `packages.core.domain.models`.
- **apps/cli/investment_tracker/ui/cli_view.py**: Fix model imports to `packages.core.domain.models`.
- **apps/cli/scheduler.py**: Merge Master's `logger` usage with `qa-testing-cli`'s `acquire_lock/release_lock`. Fix `Config` import.
- **data/active_profile.txt**: Set to `personal`.

## Verification Plan
1. `python apps/cli/main.py` - Verify dashboard loads.
2. `python apps/cli/investment_tracker/main.py` - Verify Investment Tracker runs.
3. Test FIFO sell if possible (mock/dry run).
