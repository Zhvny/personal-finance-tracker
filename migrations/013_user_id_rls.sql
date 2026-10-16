-- Migration 013: Add user_id to public financial tables + RLS policies
-- against record.user_id.
--
-- Audit A-03 (new): the previous policies (migration 006) compared
-- app.current_user_id to the literal string 'admin', and migration 012
-- dropped them as dead. This migration re-establishes per-user isolation
-- using a proper USING+WITH CHECK pair against a real user_id column.
--
-- The policies match if either:
--   (a) record.user_id = current_setting('app.current_user_id')
--   (b) the GUC is 'admin' (or unset on a connection by an admin role)
--   (c) the GUC is the empty string (no authenticated user); in that
--       case the policy denies the row. This is the fail-closed default.
--
-- The app sets ``app.current_user_id`` per-connection via set_config(..., true)
-- in services.runtime.bootstrap._service_token_middleware, called for
-- every authenticated request.

ALTER TABLE IF EXISTS public.expenses ADD COLUMN IF NOT EXISTS user_id INTEGER;
ALTER TABLE IF EXISTS public.incomes ADD COLUMN IF NOT EXISTS user_id INTEGER;
ALTER TABLE IF EXISTS public.investments ADD COLUMN IF NOT EXISTS user_id INTEGER;
ALTER TABLE IF EXISTS public.budgets ADD COLUMN IF NOT EXISTS user_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_expenses_user_id ON public.expenses(user_id);
CREATE INDEX IF NOT EXISTS idx_incomes_user_id ON public.incomes(user_id);
CREATE INDEX IF NOT EXISTS idx_investments_user_id ON public.investments(user_id);
-- public.budgets is vestigial (see migration 012 comment) and may not exist;
-- only create the index if the table is present.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'budgets') THEN
        CREATE INDEX IF NOT EXISTS idx_budgets_user_id ON public.budgets(user_id);
    END IF;
END $$;

-- RLS is already enabled on these tables (migration 006). Re-add the
-- policies with proper USING + WITH CHECK clauses.
DROP POLICY IF EXISTS expenses_user_isolation ON public.expenses;
CREATE POLICY expenses_user_isolation ON public.expenses
    FOR ALL
    USING (
        user_id::text = current_setting('app.current_user_id', true)
        OR current_setting('app.current_user_id', true) = 'admin'
    )
    WITH CHECK (
        user_id::text = current_setting('app.current_user_id', true)
        OR current_setting('app.current_user_id', true) = 'admin'
    );

DROP POLICY IF EXISTS incomes_user_isolation ON public.incomes;
CREATE POLICY incomes_user_isolation ON public.incomes
    FOR ALL
    USING (
        user_id::text = current_setting('app.current_user_id', true)
        OR current_setting('app.current_user_id', true) = 'admin'
    )
    WITH CHECK (
        user_id::text = current_setting('app.current_user_id', true)
        OR current_setting('app.current_user_id', true) = 'admin'
    );

DROP POLICY IF EXISTS investments_user_isolation ON public.investments;
CREATE POLICY investments_user_isolation ON public.investments
    FOR ALL
    USING (
        user_id::text = current_setting('app.current_user_id', true)
        OR current_setting('app.current_user_id', true) = 'admin'
    )
    WITH CHECK (
        user_id::text = current_setting('app.current_user_id', true)
        OR current_setting('app.current_user_id', true) = 'admin'
    );

DROP POLICY IF EXISTS budgets_user_isolation ON public.budgets;
-- public.budgets is vestigial and may not exist; guard the CREATE POLICY.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'budgets') THEN
        CREATE POLICY budgets_user_isolation ON public.budgets
            FOR ALL
            USING (
                user_id::text = current_setting('app.current_user_id', true)
                OR current_setting('app.current_user_id', true) = 'admin'
            )
            WITH CHECK (
                user_id::text = current_setting('app.current_user_id', true)
                OR current_setting('app.current_user_id', true) = 'admin'
            );
    END IF;
END $$;
