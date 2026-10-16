-- 018_add_user_id_per_profile.sql
-- Add user_id to per-profile financial tables (expenses/incomes/investments).
--
-- Why: the Prisma models map `userId -> user_id` on these tables, but the
-- per-profile provisioning in 015_per_profile_schema.sql created them WITHOUT
-- user_id. Prisma writes then fail with
--   DataError: column "<table>.user_id" does not exist
-- surfacing as HTTP 500 -> gateway 502 on POST /api/income|expenses|investments.
--
-- This migration is idempotent (ADD COLUMN IF NOT EXISTS) and covers the default
-- profiles. Custom profiles created later get user_id from per_profile_ddl.py,
-- which was updated in tandem. Only the schema is added; no data is touched.

DO $$
DECLARE
    profile_name TEXT;
    tbl TEXT;
    profile_names TEXT[] := ARRAY['personal', 'business'];
    tables TEXT[] := ARRAY['expenses', 'incomes', 'investments'];
BEGIN
    FOREACH profile_name IN ARRAY profile_names
    LOOP
        -- Only touch schemas that actually exist.
        IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = profile_name) THEN
            FOREACH tbl IN ARRAY tables
            LOOP
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = profile_name AND table_name = tbl
                ) THEN
                    EXECUTE format('ALTER TABLE %I.%I ADD COLUMN IF NOT EXISTS user_id INTEGER', profile_name, tbl);
                END IF;
            END LOOP;
        END IF;
    END LOOP;
END $$;
