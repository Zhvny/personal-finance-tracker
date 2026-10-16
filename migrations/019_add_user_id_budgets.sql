-- 019_add_user_id_budgets.sql
-- Add user_id to per-profile budgets tables.
--
-- Why: the Prisma Budget model maps `userId -> user_id` on `budgets`, but
-- 015_per_profile_schema.sql created budgets WITHOUT user_id (same class of bug
-- fixed for expenses/incomes/investments in 018). Reads via
-- db.budget.find_many() then fail with
--   DataError: column "budgets.user_id" does not exist
-- surfacing as HTTP 500 -> gateway 502 on GET /api/expenses/budget/{y}/{m}.
--
-- Idempotent (ADD COLUMN IF NOT EXISTS). Separate from 018 because 018 is
-- already applied; applied migrations must not be edited (checksum verify).

DO $$
DECLARE
    profile_name TEXT;
    profile_names TEXT[] := ARRAY['personal', 'business'];
BEGIN
    FOREACH profile_name IN ARRAY profile_names
    LOOP
        IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = profile_name) THEN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = profile_name AND table_name = 'budgets'
            ) THEN
                EXECUTE format('ALTER TABLE %I.budgets ADD COLUMN IF NOT EXISTS user_id INTEGER', profile_name);
            END IF;
        END IF;
    END LOOP;
END $$;
