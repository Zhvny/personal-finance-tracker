-- 020_user_id_fk_index_tz.sql
-- Canonical user_id + timezone alignment (audit Alpha, task 5).
--
-- Part A — user_id FK + index on per-profile money tables.
--   018/019 added nullable `user_id INTEGER` to personal/business
--   {expenses, incomes, investments, budgets}. This migration wires each of
--   those columns to public.users(id) (FK, no ON DELETE action: deleting a
--   user must not cascade-delete financial rows) and adds a per-table index.
--   Custom profiles provisioned later get the column from per_profile_ddl.py;
--   the FK/index below apply to whichever of personal/business exist.
--
--   NOT NULL is deliberately STAGED, not enforced here:
--     1. this migration: nullable FK + index (existing rows keep NULL);
--     2. separate backfill job assigns user_id to historical rows (NOT in this task);
--     3. follow-up migration flips the columns to NOT NULL once no NULLs remain.
--   Enforcing NOT NULL now would fail on any pre-existing NULL row.
--
-- Part B — TIMESTAMP -> TIMESTAMPTZ, narrowed to proven-UTC writers only.
--   The pre-existing rows have MIXED provenance (UTC Prisma engine writes,
--   server-local CURRENT_TIMESTAMP defaults, naive WIB app writers such as
--   PostgresOHLCVRepository.save before its UTC fix), so a blanket
--   USING ... AT TIME ZONE 'UTC' would silently shift WIB history by +7h.
--   Converted here, per profile schema (personal/business):
--     incomes.created_at
--   whose PG-side writers are exclusively the Prisma engine @default(now())
--   (engine clock is UTC). EXCLUDED and left naive until a new-column +
--   backfill migration decides them: expenses.created_at (raw recurring-sync
--   INSERT falls back to the server-local CURRENT_TIMESTAMP default),
--   investments.created_at / sell_transactions.created_at (raw psycopg2 writer
--   in investment_tracker/repository.py, DB default),
--   historical_prices.created_at (raw INSERT, DB default), every market.*
--   column incl. ohlcv_cache.fetched_at (naive local writes predate the UTC
--   writer fix), and all other profile tables (DB defaults / mixed writers).
--   DATE and TEXT columns are untouched.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, constraint added only if missing
-- (per-schema name, namespace-guarded), CREATE INDEX IF NOT EXISTS, TZ loop
-- only touches columns still timestamp-without-time-zone on real tables.

DO $$
DECLARE
    profile_name TEXT;
    tbl TEXT;
    cname TEXT;
    iname TEXT;
BEGIN
    FOREACH profile_name IN ARRAY ARRAY['personal', 'business']
    LOOP
        IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = profile_name) THEN
            CONTINUE;
        END IF;
        FOREACH tbl IN ARRAY ARRAY['expenses', 'incomes', 'investments', 'budgets']
        LOOP
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = profile_name AND table_name = tbl
            ) THEN
                CONTINUE;
            END IF;
            EXECUTE format('ALTER TABLE %I.%I ADD COLUMN IF NOT EXISTS user_id INTEGER', profile_name, tbl);
            cname := 'fk_' || profile_name || '_' || tbl || '_user_id';
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace
                WHERE c.conname = cname AND n.nspname = profile_name
            ) THEN
                EXECUTE format(
                    'ALTER TABLE %I.%I ADD CONSTRAINT %I FOREIGN KEY (user_id) REFERENCES public.users(id)',
                    profile_name, tbl, cname
                );
            END IF;
            iname := 'idx_' || profile_name || '_' || tbl || '_user_id';
            EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I.%I (user_id)', iname, profile_name, tbl);
        END LOOP;
    END LOOP;
END
$$;

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT c.table_schema, c.table_name, c.column_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        WHERE c.table_schema IN ('personal', 'business')
          AND t.table_type = 'BASE TABLE'
          AND c.data_type = 'timestamp without time zone'
          AND (c.table_name, c.column_name) IN (
              ('incomes', 'created_at')
          )
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I ALTER COLUMN %I TYPE TIMESTAMPTZ USING %I AT TIME ZONE ''UTC''',
            r.table_schema, r.table_name, r.column_name, r.column_name
        );
    END LOOP;
END
$$;
