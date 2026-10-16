# ETL Blueprint: SQLite to PostgreSQL

This document outlines the Extract, Transform, and Load (ETL) strategy for migrating decentralized SQLite data to the unified PostgreSQL server.

## 1. Migration Order
To maintain referential integrity, we must load parent tables before child tables.

1.  **Phase 1: Foundations**
    - `core.budgets`
    - `core.goals`
    - `market.ohlcv_cache`
    - `audit.audit_log`
2.  **Phase 2: Cashflow**
    - `core.incomes`
    - `core.expenses`
3.  **Phase 3: Investments**
    - `investment.investments`
    - `investment.historical_prices` (requires `investment.investments`)
    - `investment.sell_transactions` (requires `investment.investments`)
4.  **Phase 4: ML Audit**
    - `market.predictions_audit`

## 2. Transformation Rules

### Data Typing
- **Dates**: Convert SQLite `TEXT` (ISO8601) to PostgreSQL `DATE` or `TIMESTAMP`.
- **Booleans**: Convert SQLite `INTEGER` (0/1) to PostgreSQL `BOOLEAN`.
- **Money**: Convert SQLite `REAL` to PostgreSQL `DECIMAL(15,2)` to avoid floating-point rounding errors.
- **Large Objects**: `ohlcv_cache.data` (BLOB) moves to `market.ohlcv_cache.data` (BYTEA).

### Conflict Resolution
- **Historical Duplicates**: Some legacy `.db` files might exist in backup folders with overlapping data.
- **Strategy**: 
    1.  Use `apps/cli/` as the primary source for all CLI-originated data.
    2.  Use `finance-tracker-gui/data/` for GUI-specific logs/settings.
    3.  During migration, use `INSERT ... ON CONFLICT DO NOTHING` or `DO UPDATE` based on unique keys (e.g., `ticker`, `date`, `id`).

## 3. Automation Script (`tools/migrate_to_postgres.py`)
A Python script using `psycopg2` and `sqlite3` will:
1.  Iterate through the directory map.
2.  Map SQLite rows to Pydantic models.
3.  Execute batch inserts into PostgreSQL.
4.  Verify row counts.

## 4. Verification Plan
- **Row Count Check**: Sum of rows across SQLite sources must match Postgres total (minus duplicates).
- **Financial Integrity**: `SUM(amount)` in `expenses` and `incomes` must be identical before and after.
- **P/L Consistency**: Realized P/L calculation in `sell_transactions` must match GUI output.

---
07-05-2026 (22:35)
