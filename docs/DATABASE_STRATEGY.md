# Database Strategy and Architecture

## 1. Executive Summary
- **PostgreSQL** is the CANONICAL store for all financial, profile, and system data.
- **SQLite** is permitted ONLY for specific local-only read/write operations like caching, auditing, and deprecated local tools.

## 2. Migration Mechanism
The authoritative DDL is managed by the PostgreSQL migration runner (`migrations/runner.py`), tracking versions via the `public.schema_migrations` table.
- Migrations are sequential `.sql` files in the `migrations/` folder.
- Migrations are additive. To reverse, write a new rollback migration.
- `005_profile_schema_template.sql` is skipped by the runner and serves as documentation for dynamically instantiated schemas.

## 3. PostgreSQL Table Inventory

| Table | Schema | Store | Classification | Owner | Notes |
|-------|--------|-------|----------------|-------|-------|
| schema_migrations | public | PostgreSQL | SYSTEM | Runner | Tracks applied migrations |
| audit_log | audit | PostgreSQL | AUDIT | Application | Action tracking |
| profiles | system | PostgreSQL | SYSTEM | Application | Multi-profile management |
| currency_history | public | PostgreSQL | N8N | n8n Workflows | Populated automatically |
| asset_price_history | public | PostgreSQL | N8N | n8n Workflows | Populated automatically |
| expenses | {profile} | PostgreSQL | CANONICAL | SchemaInitializer | Profile-scoped |
| incomes | {profile} | PostgreSQL | CANONICAL | SchemaInitializer | Profile-scoped |
| investments | {profile} | PostgreSQL | CANONICAL | SchemaInitializer | Profile-scoped |
| ... | {profile} | PostgreSQL | CANONICAL | SchemaInitializer | Other profile tables |
| covariance_cache | market | PostgreSQL | CACHE | MarketScheduler | Market covariance cache |
| market_data | market | PostgreSQL | CACHE | MarketScheduler | Aggregated market data |

## 4. SQLite Files Inventory

| File | Store | Classification | Owner | Notes |
|------|-------|----------------|-------|-------|
| expense.db | file | LEGACY/DEPRECATED | CLI | Read-only legacy import path |
| income.db | file | LEGACY/DEPRECATED | CLI | Read-only legacy import path |
| audit_log.db | file | AUDIT | security/core | Local action audits |
| behavioral.db | file | SNAPSHOT | behavioral | Snapshot states |

## 5. Profile Schema Strategy
PostgreSQL leverages schema-based multi-tenancy. Rather than adding a `profile_id` to every table, a completely isolated schema (e.g., `user_zhvn`) is created per profile. The application routes queries to the correct schema. This is handled dynamically by `SchemaInitializer` using the `005_profile_schema_template.sql` definition.

## 6. How to Add a Migration
Add a sequentially numbered file in the `migrations/` directory (e.g. `006_some_update.sql`). Run `python migrations/runner.py apply`.

## 7. Rollback Strategy
Rollbacks must be implemented as new "forward" migrations. Modifying applied `.sql` files will break the `runner.py verify` checksum validation.

## 8. Backup and Recovery
PostgreSQL data should be backed up using `pg_dump`. Since profiles use schemas, the entire database can be dumped together or per-schema.

## 9. Audit Log Retention
Retention is a manual purge via `scripts/retention/audit_logs_purge.py` (see migration 014): PII columns are NULLed after the 90-day dispute window while rows stay for the audit trail. No cron is scheduled yet; a recurring schedule follows separately. No scheduler changes in this task.
