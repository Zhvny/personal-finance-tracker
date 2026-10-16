-- Migration 012: Drop dead RLS policies (audit A-C03)
--
-- The policies added in migration 006 were:
--   USING (current_setting('app.current_user_id', true) = 'admin')
-- and no code path in the codebase ever set the GUC. Effect: every
-- non-admin connection saw zero rows from public.expenses/incomes/
-- investments/budgets.
--
-- These policies were always-dead in production because:
--   1. The actual financial data lives in per-profile schemas (e.g.
--      {PROFILE}.expenses, per migration 005), not in public.expenses.
--   2. public.expenses/incomes/investments/budgets are empty in the
--      canonical schema — they're vestigial from an earlier design.
--   3. Cross-user isolation is enforced by routing each user's queries
--      to their own profile schema (Config.get_active_profile()), not
--      by row-level policies.
--
-- Followed by migration 013 which re-adds the policies with proper
-- USING+WITH CHECK against record.user_id (now that the GUC plumbing
-- in services.runtime.bootstrap is in place).

DROP POLICY IF EXISTS expenses_user_isolation ON public.expenses;
DROP POLICY IF EXISTS incomes_user_isolation ON public.incomes;
DROP POLICY IF EXISTS investments_user_isolation ON public.investments;
DROP POLICY IF EXISTS budgets_user_isolation ON public.budgets;
