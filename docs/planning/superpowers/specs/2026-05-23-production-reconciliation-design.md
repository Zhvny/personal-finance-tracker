Last Updated: 29-05-2026 (14:30)

# Design Spec: Reconciling Production Logic into Monorepo Structure

## 1. Overview
Batch reconcile production logic from deprecated top-level folders into the new `packages/core/src/` monorepo structure. This ensures advanced features (async, postgres, investment analytics) are preserved while aligning with the clean architecture layout.

## 2. File Mapping

### 2.1 Application Layer
| Source (`packages/core/application/`) | Target (`packages/core/src/application/`) | Domain |
| --- | --- | --- |
| `butterfly_service.py` | `investment_tracker/butterfly_service.py` | Investment |
| `butterfly_schemas.py` | `investment_tracker/butterfly_schemas.py` | Investment |
| `investment_service.py` | `investment_tracker/investment_service.py` | Investment |
| `market_data_service.py` | `investment_tracker/market_data_service.py` | Investment |
| `whale_analysis_service.py` | `investment_tracker/whale_analysis_service.py` | Investment |
| `expense_service.py` | `expense_tracker/expense_service.py` | Expense |
| `income_service.py` | `income_tracker/income_service.py` | Income |
| `reward_service.py` | `shared/reward_service.py` | Shared |
| `profile_service.py` | `shared/profile_service.py` | Shared |
| `maintenance_service.py` | `shared/maintenance_service.py` | Shared |
| `business_report_service.py` | `shared/business_report_service.py` | Shared |
| `dashboard_service.py` | `shared/dashboard_service.py` | Shared |

### 2.2 Infrastructure Layer
| Source (`packages/core/infrastructure/`) | Target (`packages/core/src/infrastructure/`) | Category |
| --- | --- | --- |
| `persistence/database.py` | `shared/persistence/database.py` | Persistence |
| `persistence/postgres_ohlcv_repository.py` | `shared/persistence/postgres_ohlcv_repository.py` | Persistence |
| `cache/butterfly_cache.py` | `shared/cache/butterfly_cache.py` | Cache |
| `config.py` | `shared/config.py` | Config |

## 3. Import Strategy
Relative imports will be updated to reflect the new depth:
- `application` -> `infrastructure` moves from `..infrastructure` to `...infrastructure.shared`.
- `application` -> `domain` moves from `..domain` to `...domain.shared`.

## 4. Cleanup Plan
Once files are moved and imports verified:
1. Delete `packages/core/application/`
2. Delete `packages/core/domain/`
3. Delete `packages/core/infrastructure/`
4. Update `run-cli.bat` and entry points if they rely on old paths.

## 5. Verification
1. Run `pytest` to ensure logic remains intact.
2. Run `run-cli.bat` to verify basic functionality.
