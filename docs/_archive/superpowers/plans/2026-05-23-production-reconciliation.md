Last Updated: 29-05-2026 (14:30)

# Production Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move core application and infrastructure logic to the new `packages/core/src/` monorepo structure and fix imports to preserve production functionality.

**Architecture:** Use the clean architecture layout established in Phase 1 & 2. Move files from deprecated top-level folders (`application`, `infrastructure`) to domain-specific or shared folders under `src`.

**Tech Stack:** Python, Pandas, Asyncio, Postgres.

---

### Task 1: Reconcile Infrastructure Logic

**Files:**
- Create: `packages/core/src/infrastructure/shared/persistence/database.py`
- Create: `packages/core/src/infrastructure/shared/persistence/postgres_ohlcv_repository.py`
- Create: `packages/core/src/infrastructure/shared/cache/butterfly_cache.py`
- Create: `packages/core/src/infrastructure/shared/config.py`

- [ ] **Step 1: Move Database persistence logic**
  Move `packages/core/infrastructure/persistence/database.py` to `packages/core/src/infrastructure/shared/persistence/database.py`.

- [ ] **Step 2: Move Postgres OHLCV Repository logic**
  Move `packages/core/infrastructure/persistence/postgres_ohlcv_repository.py` to `packages/core/src/infrastructure/shared/persistence/postgres_ohlcv_repository.py`.

- [ ] **Step 3: Move Butterfly Cache logic**
  Move `packages/core/infrastructure/cache/butterfly_cache.py` to `packages/core/src/infrastructure/shared/cache/butterfly_cache.py`.

- [ ] **Step 4: Move Config logic**
  Move `packages/core/infrastructure/config.py` to `packages/core/src/infrastructure/shared/config.py`.

- [ ] **Step 5: Verify files exist in target locations**
  Run: `ls packages/core/src/infrastructure/shared/persistence/`

---

### Task 2: Reconcile Application Logic (Investment Domain)

**Files:**
- Create: `packages/core/src/application/investment_tracker/butterfly_service.py`
- Create: `packages/core/src/application/investment_tracker/butterfly_schemas.py`
- Create: `packages/core/src/application/investment_tracker/investment_service.py`
- Create: `packages/core/src/application/investment_tracker/market_data_service.py`
- Create: `packages/core/src/application/investment_tracker/whale_analysis_service.py`

- [ ] **Step 1: Move Butterfly Service and Schemas**
  Move `packages/core/application/butterfly_service.py` and `packages/core/application/butterfly_schemas.py` to `packages/core/src/application/investment_tracker/`.

- [ ] **Step 2: Move Investment and Market Data services**
  Move `packages/core/application/investment_service.py`, `packages/core/application/market_data_service.py`, and `packages/core/application/whale_analysis_service.py` to `packages/core/src/application/investment_tracker/`.

- [ ] **Step 3: Fix imports in `butterfly_service.py`**
  Update `packages/core/src/application/investment_tracker/butterfly_service.py` imports.
  From:
  ```python
  from .butterfly_schemas import ButterflyNode, ButterflyEdge, ButterflyResponse
  from ..infrastructure.persistence.postgres_ohlcv_repository import PostgresOHLCVRepository
  from ..infrastructure.cache.butterfly_cache import ButterflyCache
  ```
  To:
  ```python
  from .butterfly_schemas import ButterflyNode, ButterflyEdge, ButterflyResponse
  from ...infrastructure.shared.persistence.postgres_ohlcv_repository import PostgresOHLCVRepository
  from ...infrastructure.shared.cache.butterfly_cache import ButterflyCache
  ```

---

### Task 3: Reconcile Remaining Application Logic

**Files:**
- Create: `packages/core/src/application/expense_tracker/expense_service.py`
- Create: `packages/core/src/application/income_tracker/income_service.py`
- Create: `packages/core/src/application/shared/reward_service.py`
- Create: `packages/core/src/application/shared/profile_service.py`
- Create: `packages/core/src/application/shared/maintenance_service.py`
- Create: `packages/core/src/application/shared/business_report_service.py`
- Create: `packages/core/src/application/shared/dashboard_service.py`

- [ ] **Step 1: Move Tracker services**
  Move `packages/core/application/expense_service.py` to `packages/core/src/application/expense_tracker/expense_service.py`.
  Move `packages/core/application/income_service.py` to `packages/core/src/application/income_tracker/income_service.py`.

- [ ] **Step 2: Move Shared services**
  Move `packages/core/application/reward_service.py`, `packages/core/application/profile_service.py`, `packages/core/application/maintenance_service.py`, `packages/core/application/business_report_service.py`, and `packages/core/application/dashboard_service.py` to `packages/core/src/application/shared/`.

---

### Task 4: Cleanup and Final Verification

- [ ] **Step 1: Delete deprecated folders**
  Run: `rm -rf packages/core/application packages/core/domain packages/core/infrastructure`

- [ ] **Step 2: Run tests**
  Run: `pytest`

- [ ] **Step 3: Verify CLI entry point**
  Run: `run-cli.bat`
