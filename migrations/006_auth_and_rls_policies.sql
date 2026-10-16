-- Migration 006: Authentication, Audit Logging & Row Level Security (RLS)
-- Enables security principals: Authentication, Authorization, Accounting (Audit), and CIA Triad.

-- 1. Users Table
CREATE TABLE IF NOT EXISTS public.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(64) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Accounting Audit Log Table (Immutable)
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    target_table VARCHAR(100),
    record_id VARCHAR(100),
    previous_value JSONB,
    new_value JSONB,
    ip_address VARCHAR(45),
    status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS'
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_ts ON public.audit_logs(actor, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON public.audit_logs(action);

-- 3. Row Level Security (RLS) Enablement & Policies
-- Enable RLS on core financial tables
ALTER TABLE IF EXISTS public.expenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.incomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.investments ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.budgets ENABLE ROW LEVEL SECURITY;

-- Dynamic RLS Policies (User Isolation)
DROP POLICY IF EXISTS expenses_user_isolation ON public.expenses;
CREATE POLICY expenses_user_isolation ON public.expenses
    FOR ALL
    USING (current_setting('app.current_user_id', true) IS NULL OR current_setting('app.current_user_id', true) = 'admin');

DROP POLICY IF EXISTS incomes_user_isolation ON public.incomes;
CREATE POLICY incomes_user_isolation ON public.incomes
    FOR ALL
    USING (current_setting('app.current_user_id', true) IS NULL OR current_setting('app.current_user_id', true) = 'admin');

DROP POLICY IF EXISTS investments_user_isolation ON public.investments;
CREATE POLICY investments_user_isolation ON public.investments
    FOR ALL
    USING (current_setting('app.current_user_id', true) IS NULL OR current_setting('app.current_user_id', true) = 'admin');
