-- 016_service_schemas.sql
-- Per-service schema isolation: move domain tables from public into
-- service-specific schemas. Shared tables (sessions, audit_log, etc.)
-- remain in public.
--
-- Idempotent: CREATE SCHEMA IF NOT EXISTS + ALTER TABLE IF EXISTS
-- (via DO block + exception handling).

DO $$
BEGIN
    -- Create service schemas
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS alpha_platform';
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS alpha_ledger';
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS alpha_portfolio';
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS alpha_market';
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS alpha_insights';
    EXECUTE 'CREATE SCHEMA IF NOT EXISTS alpha_engagement';

    -- Move platform tables
    BEGIN
        EXECUTE 'ALTER TABLE IF EXISTS public.user_stats SET SCHEMA alpha_platform';
    EXCEPTION WHEN undefined_table OR duplicate_table THEN NULL;
    END;

    BEGIN
        EXECUTE 'ALTER TABLE IF EXISTS public.business_projects SET SCHEMA alpha_platform';
    EXCEPTION WHEN undefined_table OR duplicate_table THEN NULL;
    END;

    BEGIN
        EXECUTE 'ALTER TABLE IF EXISTS public.daily_progress_logs SET SCHEMA alpha_platform';
    EXCEPTION WHEN undefined_table OR duplicate_table THEN NULL;
    END;

    BEGIN
        EXECUTE 'ALTER TABLE IF EXISTS public.labor_attendance_logs SET SCHEMA alpha_platform';
    EXCEPTION WHEN undefined_table OR duplicate_table THEN NULL;
    END;

    BEGIN
        EXECUTE 'ALTER TABLE IF EXISTS public.project_milestones SET SCHEMA alpha_platform';
    EXCEPTION WHEN undefined_table OR duplicate_table THEN NULL;
    END;

    -- Move ledger tables
    BEGIN
        EXECUTE 'ALTER TABLE IF EXISTS public.expenses SET SCHEMA alpha_ledger';
    EXCEPTION WHEN undefined_table OR duplicate_table THEN NULL;
    END;

    BEGIN
        EXECUTE 'ALTER TABLE IF EXISTS public.incomes SET SCHEMA alpha_ledger';
    EXCEPTION WHEN undefined_table OR duplicate_table THEN NULL;
    END;

    BEGIN
        EXECUTE 'ALTER TABLE IF EXISTS public.budgets SET SCHEMA alpha_ledger';
    EXCEPTION WHEN undefined_table OR duplicate_table THEN NULL;
    END;

    -- Move portfolio tables
    BEGIN
        EXECUTE 'ALTER TABLE IF EXISTS public.investments SET SCHEMA alpha_portfolio';
    EXCEPTION WHEN undefined_table OR duplicate_table THEN NULL;
    END;

    BEGIN
        EXECUTE 'ALTER TABLE IF EXISTS public.sell_transactions SET SCHEMA alpha_portfolio';
    EXCEPTION WHEN undefined_table OR duplicate_table THEN NULL;
    END;

    BEGIN
        EXECUTE 'ALTER TABLE IF EXISTS public.historical_prices SET SCHEMA alpha_portfolio';
    EXCEPTION WHEN undefined_table OR duplicate_table THEN NULL;
    END;
END $$;
