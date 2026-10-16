# Phase 2 — Database Authority Inventory

## Decision

PostgreSQL is the canonical store for financial and profile state. SQLite is
not an availability fallback for this state. A PostgreSQL error must remain
observable to the caller.

This document is an inventory and migration boundary, not a data-migration
record. No legacy SQLite database may be deleted until its rows, totals, and
relationships have been validated against PostgreSQL.

## Classification

| Data | Classification | Current authoritative target | Notes |
| --- | --- | --- | --- |
| expenses, incomes, investments, sell_transactions | CANONICAL POSTGRES | active profile schema | Financial ledgers. |
| historical_prices, fx_rates, recurrence_candidates | CANONICAL POSTGRES | active profile schema | Related financial/market state. |
| budgets, goals, virtual_accounts, manual_balances, cash_split, transfer_log | CANONICAL POSTGRES | active profile schema | Financial planning and balance state. |
| user_stats, reward_state, behavioral_snapshots, networth_snapshots, stock_favorites | CANONICAL POSTGRES | active profile schema | Profile state; migration ownership still needs consolidation. |
| ohlcv_cache, covariance_cache, latest_prices, butterfly_cache | CACHE | PostgreSQL or local SQLite cache | Rebuildable data; SQLite is permitted only when explicitly labelled cache. |
| audit_log, evolution_logs, receipt export log, merchant memory | AUDIT / LOCAL FEATURE | local SQLite today | Not a financial ledger; retain until a separate retention and privacy decision. |
| CLI `expense.db`, `income.db`, `portfolio.db`, `goals.db`, `budget.db` | LEGACY SQLITE | none | Must not receive canonical financial reads or writes. |
| `alpha_db_schema.sql` tables, Prisma models, startup DDL | UNKNOWN / SCHEMA DRIFT | none | Competing definitions; must be reconciled before migration cutover. |

## Verified schema owners

The following sources currently define overlapping PostgreSQL tables:

1. `packages/database/schema.prisma` — Prisma models.
2. `packages/api/backend/infrastructure/schemas.py` — API-startup, profile-schema DDL.
3. `scripts/setup_postgres.py` and `alpha_db_schema.sql` — raw setup DDL.
4. `scripts/migrations/` — isolated one-off migrations.

This means there is no versioned authoritative migration mechanism yet. Do not
remove startup DDL or legacy SQLite paths until a migration baseline is chosen,
version tracking is implemented, and a repeatable schema-drift check passes.

## Required cutover sequence

1. Choose one migration owner and baseline the active PostgreSQL profile schema.
2. Make startup schema code validation-only after the baseline is deployed.
3. Back up each legacy SQLite file before importing it.
4. Reconcile row counts, financial totals, and foreign-key relationships.
5. Redirect each CLI repository to a PostgreSQL implementation.
6. Keep legacy SQLite read-only for a defined rollback window; then archive it.

## Known blockers

- The CLI investment repository still performs direct SQLite writes.
- Prisma, profile startup DDL, and fixed-schema setup SQL do not yet have a
  demonstrated parity contract.
- Tests cannot be executed in this environment because no Python interpreter
  is available on PATH.
