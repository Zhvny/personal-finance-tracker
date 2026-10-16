# Database Migrations System

This directory contains the authoritative PostgreSQL migration system for the Alpha Finance Tracker.

## Database Strategy

- **PostgreSQL** is the canonical store for all relational data.
- **SQLite** is strictly limited to local-only functions (audit logs, behavioral snapshots, cache).

## How to use the Runner

The `runner.py` script manages applying migrations:

```bash
# Check status of migrations (Applied/Pending)
python migrations/runner.py status

# Apply all pending migrations sequentially
python migrations/runner.py apply

# Verify checksums of applied migrations against current files
python migrations/runner.py verify
```

## Migration Files Overview

- `001_schema_version_table.sql`: Bootstraps the `schema_migrations` table and shared schemas/tables (audit, system profiles).
- `002_n8n_automation_tables.sql`: Financial data tables populated by n8n workflows (currency/asset history).
- `003_market_schema.sql`: Market data cache and structures.
- `004_add_composite_indexes.sql`: Cross-table and performance optimizations.
- `005_profile_schema_template.sql`: **TEMPLATE ONLY**. Not run by the runner. Documents the per-profile schema dynamically applied by `SchemaInitializer`.
- `006_auth_and_rls_policies.sql`: Authentication tables and row-level-security policies.
- `007_ohlcv_cache_and_recurrence_reconcile.sql`: Adds `market.ohlcv_cache` / `market.latest_prices` and reconciles `recurrence_candidates` across existing profile schemas.
- `008_transaction_account_model.sql`: Unified transaction & account model (Phase 2) — `accounts`, `categories`, `merchants`, `transactions` (type/source/confidence/idempotency_key), double-entry `transfer_pairs` across existing profile schemas; relaxes the legacy duplicate-blocking UNIQUE constraints on `expenses`/`incomes` (duplicate protection moved to `transactions.idempotency_key`).
- `009_telegram_confirmation_model.sql`: Persistent Telegram confirmation store (Phase 3) — global `chat_bindings` (per-chat profile binding) and `pending_confirmations` (draft -> confirm/cancel lifecycle, one-time token, 24h expiry, ledger idempotency).
- `010_goals_schema_reconcile.sql`: Aligns deployed per-profile `goals` tables with the canonical Phase 8 shape (adds `name`/`target_date`, relaxes legacy NOT NULL `title`) so `goals_service` writes succeed on pre-005 deployed profiles.

## Adding New Migrations

1. Create a new `.sql` file with the next sequential prefix (e.g., `010_add_new_feature.sql`).
2. Do not modify existing applied migration files (this will cause `verify` to fail).
3. Always test your migration locally before merging.
