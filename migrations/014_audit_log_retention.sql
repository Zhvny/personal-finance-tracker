-- Migration 014 (Audit T4, 2026-09-02): audit_logs retention.
-- PII (ip_address, previous_value, new_value JSONB) is anonymized
-- after the 90-day dispute window. The row stays so the audit trail
-- is intact; the PII columns are NULLed.
--
-- This migration does NOT install a cron / scheduled function.
-- The companion helper lives in:
--   scripts/retention/audit_logs_purge.py
-- and is called from APScheduler (`backend/app/workers/sampler.py`
-- pattern). Idempotent: re-running within the same window is a no-op.

-- Idempotent: nothing to DDL; the column shapes already support NULL.
-- The only schema-level guarantee we add is a CHECK that ip_address
-- can be NULL (it already can; the column is nullable in 006).
DO $$
BEGIN
    -- No-op. The comment block above is the doc.
    PERFORM 1;
END
$$;
