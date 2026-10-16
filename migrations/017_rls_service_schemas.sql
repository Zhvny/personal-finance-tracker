-- Migration 017: Row Level Security (RLS) for service schemas
-- Enforces service-level isolation so each service can only access
-- tables in its own schema (alpha_<service>).
--
-- Uses a session GUC `app.service_name` that each service sets on
-- its connection at startup (e.g. SET LOCAL app.service_name = 'ledger').
--
-- Idempotent: DROP POLICY IF EXISTS + CREATE POLICY, wrapped in
-- exception handling for tables that may not exist yet.

-- ============================================================
-- alpha_platform: platform service
-- ============================================================
ALTER TABLE IF EXISTS alpha_platform.user_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS alpha_platform.business_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS alpha_platform.daily_progress_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS alpha_platform.labor_attendance_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS alpha_platform.project_milestones ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    DROP POLICY IF EXISTS platform_service_isolation ON alpha_platform.user_stats;
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    DROP POLICY IF EXISTS platform_service_isolation_bp ON alpha_platform.business_projects;
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    DROP POLICY IF EXISTS platform_service_isolation_dpl ON alpha_platform.daily_progress_logs;
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    DROP POLICY IF EXISTS platform_service_isolation_lal ON alpha_platform.labor_attendance_logs;
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    DROP POLICY IF EXISTS platform_service_isolation_pm ON alpha_platform.project_milestones;
EXCEPTION WHEN undefined_table THEN NULL; END; $$;

DO $$
BEGIN
    CREATE POLICY platform_service_isolation ON alpha_platform.user_stats
        FOR ALL
        USING (current_setting('app.service_name', true) = 'platform');
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    CREATE POLICY platform_service_isolation_bp ON alpha_platform.business_projects
        FOR ALL
        USING (current_setting('app.service_name', true) = 'platform');
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    CREATE POLICY platform_service_isolation_dpl ON alpha_platform.daily_progress_logs
        FOR ALL
        USING (current_setting('app.service_name', true) = 'platform');
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    CREATE POLICY platform_service_isolation_lal ON alpha_platform.labor_attendance_logs
        FOR ALL
        USING (current_setting('app.service_name', true) = 'platform');
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    CREATE POLICY platform_service_isolation_pm ON alpha_platform.project_milestones
        FOR ALL
        USING (current_setting('app.service_name', true) = 'platform');
EXCEPTION WHEN undefined_table THEN NULL; END; $$;

-- ============================================================
-- alpha_ledger: ledger service
-- ============================================================
ALTER TABLE IF EXISTS alpha_ledger.expenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS alpha_ledger.incomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS alpha_ledger.budgets ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    DROP POLICY IF EXISTS ledger_service_isolation_exp ON alpha_ledger.expenses;
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    DROP POLICY IF EXISTS ledger_service_isolation_inc ON alpha_ledger.incomes;
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    DROP POLICY IF EXISTS ledger_service_isolation_bud ON alpha_ledger.budgets;
EXCEPTION WHEN undefined_table THEN NULL; END; $$;

DO $$
BEGIN
    CREATE POLICY ledger_service_isolation_exp ON alpha_ledger.expenses
        FOR ALL
        USING (current_setting('app.service_name', true) = 'ledger');
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    CREATE POLICY ledger_service_isolation_inc ON alpha_ledger.incomes
        FOR ALL
        USING (current_setting('app.service_name', true) = 'ledger');
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    CREATE POLICY ledger_service_isolation_bud ON alpha_ledger.budgets
        FOR ALL
        USING (current_setting('app.service_name', true) = 'ledger');
EXCEPTION WHEN undefined_table THEN NULL; END; $$;

-- ============================================================
-- alpha_portfolio: portfolio service
-- ============================================================
ALTER TABLE IF EXISTS alpha_portfolio.investments ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS alpha_portfolio.sell_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS alpha_portfolio.historical_prices ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    DROP POLICY IF EXISTS portfolio_service_isolation_inv ON alpha_portfolio.investments;
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    DROP POLICY IF EXISTS portfolio_service_isolation_st ON alpha_portfolio.sell_transactions;
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    DROP POLICY IF EXISTS portfolio_service_isolation_hp ON alpha_portfolio.historical_prices;
EXCEPTION WHEN undefined_table THEN NULL; END; $$;

DO $$
BEGIN
    CREATE POLICY portfolio_service_isolation_inv ON alpha_portfolio.investments
        FOR ALL
        USING (current_setting('app.service_name', true) = 'portfolio');
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    CREATE POLICY portfolio_service_isolation_st ON alpha_portfolio.sell_transactions
        FOR ALL
        USING (current_setting('app.service_name', true) = 'portfolio');
EXCEPTION WHEN undefined_table THEN NULL; END; $$;
DO $$
BEGIN
    CREATE POLICY portfolio_service_isolation_hp ON alpha_portfolio.historical_prices
        FOR ALL
        USING (current_setting('app.service_name', true) = 'portfolio');
EXCEPTION WHEN undefined_table THEN NULL; END; $$;

-- ============================================================
-- alpha_market, alpha_insights, alpha_engagement:
-- RLS enabled by the owning service when it creates its tables.
-- No existing tables to protect here; policies can be added
-- by the service when new domain tables are introduced.
-- ============================================================
