-- 007: Market OHLCV/latest-price tables + reconcile recurrence_candidates DDL
--
-- 1. market.ohlcv_cache   — written by PostgresOHLCVRepository.save()
--    (INSERT ... ON CONFLICT (ticker, period) DO UPDATE)
-- 2. market.latest_prices — written by PostgresMarketDataRepository.save()
--    (INSERT ... ON CONFLICT (ticker) DO UPDATE)
-- 3. Per-profile recurrence_candidates tables were historically created with
--    two different layouts (template 005 vs packages/api/backend/expenses/
--    recurrence_detector.py). This migration unions both layouts so the
--    detector's persist/confirm SQL works against every existing profile.

CREATE SCHEMA IF NOT EXISTS market;

CREATE TABLE IF NOT EXISTS market.ohlcv_cache (
    ticker TEXT NOT NULL,
    period TEXT NOT NULL,
    fetched_at TIMESTAMP,
    data BYTEA,
    PRIMARY KEY (ticker, period)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_cache_ticker
    ON market.ohlcv_cache (ticker);

CREATE TABLE IF NOT EXISTS market.latest_prices (
    ticker TEXT PRIMARY KEY,
    price DECIMAL(20, 8),
    timestamp TIMESTAMP,
    change_pct DECIMAL(10, 4),
    volume BIGINT,
    metadata TEXT
);

-- Reconcile recurrence_candidates across every profile schema.
DO $$
DECLARE
    s TEXT;
BEGIN
    FOR s IN
        SELECT nspname
        FROM pg_namespace
        WHERE nspname NOT LIKE 'pg\_%'
          AND nspname NOT IN (
              'information_schema', 'public', 'audit', 'system',
              'core', 'financials', 'investment', 'market'
          )
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = s AND table_name = 'recurrence_candidates'
        ) THEN
            EXECUTE format('ALTER TABLE %I.recurrence_candidates ADD COLUMN IF NOT EXISTS amount NUMERIC(15,2)', s);
            EXECUTE format('ALTER TABLE %I.recurrence_candidates ADD COLUMN IF NOT EXISTS avg_amount DOUBLE PRECISION', s);
            EXECUTE format('ALTER TABLE %I.recurrence_candidates ADD COLUMN IF NOT EXISTS occurrences INTEGER', s);
            EXECUTE format('ALTER TABLE %I.recurrence_candidates ADD COLUMN IF NOT EXISTS is_confirmed BOOLEAN NOT NULL DEFAULT FALSE', s);
            EXECUTE format('ALTER TABLE %I.recurrence_candidates ADD COLUMN IF NOT EXISTS status TEXT DEFAULT ''pending''', s);
            EXECUTE format('ALTER TABLE %I.recurrence_candidates ADD COLUMN IF NOT EXISTS updated_at TEXT', s);
        END IF;
    END LOOP;
END $$;
