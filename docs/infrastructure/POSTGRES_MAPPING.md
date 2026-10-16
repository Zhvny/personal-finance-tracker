# PostgreSQL Schema Mapping

This document maps existing SQLite tables to a unified PostgreSQL schema for the `finance_tracker` database.

## Unified Database Structure
- **Database Name**: `finance_tracker`
- **Schema Strategy**: Modular schemas per domain (e.g., `core`, `investment`, `market`, `audit`).

---

## 1. Schema: `core` (Budget, Goals, Expenses, Income)

### Table: `expenses` (Source: `expense.db`)
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PRIMARY KEY | |
| `amount` | DECIMAL(15,2) | |
| `description` | TEXT | |
| `category` | VARCHAR(50) | |
| `payment_method` | VARCHAR(50) | |
| `date` | DATE | |
| `is_recurring` | BOOLEAN | |
| `recurring_period` | VARCHAR(20) | |
| `created_at` | TIMESTAMP | DEFAULT NOW() |

### Table: `incomes` (Source: `income.db`)
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PRIMARY KEY | |
| `amount` | DECIMAL(15,2) | |
| `source` | TEXT | |
| `income_type` | VARCHAR(50) | |
| `date` | DATE | |
| `description` | TEXT | |
| `is_taxed` | BOOLEAN | |
| `created_at` | TIMESTAMP | DEFAULT NOW() |

### Table: `budgets` (Source: `budget.db`)
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PRIMARY KEY | |
| `year` | INTEGER | |
| `month` | INTEGER | |
| `category` | VARCHAR(50) | |
| `limit_amt` | DECIMAL(15,2) | |
| `UNIQUE(year, month, category)` | | |

### Table: `goals` (Source: `goals.db`)
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PRIMARY KEY | |
| `name` | TEXT | |
| `target_amount` | DECIMAL(15,2) | |
| `current_amount` | DECIMAL(15,2) | |
| `target_date` | DATE | |
| `created_at` | TIMESTAMP | |

---

## 2. Schema: `investment`

### Table: `investments` (Source: `portfolio.db`)
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PRIMARY KEY | |
| `asset_type` | VARCHAR(20) | |
| `ticker` | VARCHAR(20) | |
| `quantity` | DECIMAL(20,8) | |
| `buy_price` | DECIMAL(20,4) | |
| `buy_currency` | CHAR(3) | |
| `buy_date` | DATE | |
| `status` | VARCHAR(20) | 'holding', 'sold' |
| `remaining_quantity` | DECIMAL(20,8) | |
| `created_at` | TIMESTAMP | |

### Table: `historical_prices`
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PRIMARY KEY | |
| `investment_id` | INTEGER | FK -> investments.id |
| `snapshot_date` | DATE | |
| `price_usd` | DECIMAL(20,4) | |
| `price_idr` | DECIMAL(20,4) | |

---

## 3. Schema: `market` (Caching & Intelligence)

### Table: `ohlcv_cache`
| Column | Type | Notes |
|---|---|---|
| `ticker` | VARCHAR(20) | |
| `period` | VARCHAR(10) | |
| `fetched_at` | TIMESTAMP | |
| `data` | BYTEA | Compressed binary data |
| `PRIMARY KEY (ticker, period)` | | |

### Table: `predictions_audit` (Source: `ml_audit.db`)
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PRIMARY KEY | |
| `ticker` | VARCHAR(20) | |
| `category` | VARCHAR(20) | |
| `last_close` | DECIMAL(20,4) | |
| `target_price` | DECIMAL(20,4) | |
| `pred_return` | DECIMAL(10,6) | |
| `confidence` | DECIMAL(5,4) | |
| `timestamp` | TIMESTAMP | |
| `actual_close_h1` | DECIMAL(20,4) | |
| `is_correct` | BOOLEAN | |

---

## 4. Schema: `audit`

### Table: `audit_log`
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PRIMARY KEY | |
| `ts` | TIMESTAMP | |
| `ip` | INET | |
| `method` | VARCHAR(10) | |
| `path` | TEXT | |
| `status_code` | INTEGER | |
| `latency_ms` | REAL | |
| `user_agent` | TEXT | |
| `detail` | JSONB | |

---
07-05-2026 (22:35)
