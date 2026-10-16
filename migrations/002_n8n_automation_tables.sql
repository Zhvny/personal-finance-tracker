-- These tables are written by n8n workflows and read by the API. Schema: public.

CREATE TABLE IF NOT EXISTS public.currency_history (
    id                BIGSERIAL PRIMARY KEY,
    base_currency     VARCHAR(10)     NOT NULL,          -- e.g. USD
    target_currency   VARCHAR(10)     NOT NULL,          -- e.g. IDR, EUR, JPY
    rate              NUMERIC(20, 6)  NOT NULL,          -- exchange rate
    threshold         NUMERIC(20, 6),                    -- configured alert threshold
    alert_triggered   BOOLEAN         NOT NULL DEFAULT FALSE,
    fetched_at        TIMESTAMPTZ     NOT NULL,
    date              DATE            NOT NULL,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_currency_history_pair_date
    ON public.currency_history (base_currency, target_currency, date DESC);

CREATE INDEX IF NOT EXISTS idx_currency_history_alert
    ON public.currency_history (alert_triggered, fetched_at DESC)
    WHERE alert_triggered = TRUE;

CREATE TABLE IF NOT EXISTS public.asset_price_history (
    id                BIGSERIAL PRIMARY KEY,
    asset_symbol      VARCHAR(30)     NOT NULL,          -- e.g. BTC, AAPL, GOLD
    asset_name        VARCHAR(200)    NOT NULL,
    asset_type        VARCHAR(30)     NOT NULL,          -- stocks | crypto | commodity
    current_price     NUMERIC(20, 6)  NOT NULL,
    currency          VARCHAR(10)     NOT NULL DEFAULT 'USD',
    target_price      NUMERIC(20, 6)  NOT NULL,
    price_below_target BOOLEAN        NOT NULL DEFAULT FALSE,
    source            VARCHAR(100),                      -- coingecko | yahoo_finance | scraper
    recorded_at       TIMESTAMPTZ     NOT NULL,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_asset_price_symbol_time
    ON public.asset_price_history (asset_symbol, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_asset_price_type
    ON public.asset_price_history (asset_type, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_asset_price_below_target
    ON public.asset_price_history (price_below_target, recorded_at DESC)
    WHERE price_below_target = TRUE;

CREATE OR REPLACE VIEW public.v_latest_currency_rates AS
SELECT DISTINCT ON (base_currency, target_currency)
    base_currency,
    target_currency,
    rate,
    threshold,
    alert_triggered,
    fetched_at
FROM public.currency_history
ORDER BY base_currency, target_currency, fetched_at DESC;

CREATE OR REPLACE VIEW public.v_latest_asset_prices AS
SELECT DISTINCT ON (asset_symbol)
    asset_symbol,
    asset_name,
    asset_type,
    current_price,
    currency,
    target_price,
    price_below_target,
    source,
    recorded_at
FROM public.asset_price_history
ORDER BY asset_symbol, recorded_at DESC;

CREATE OR REPLACE VIEW public.v_recent_alerts AS
SELECT
    'currency' AS monitor_type,
    base_currency || '/' || target_currency AS asset,
    rate::TEXT AS current_value,
    threshold::TEXT AS target_value,
    fetched_at AS triggered_at
FROM public.currency_history
WHERE alert_triggered = TRUE
  AND fetched_at >= NOW() - INTERVAL '24 hours'
UNION ALL
SELECT
    'price_monitor' AS monitor_type,
    asset_symbol AS asset,
    current_price::TEXT AS current_value,
    target_price::TEXT AS target_value,
    recorded_at AS triggered_at
FROM public.asset_price_history
WHERE price_below_target = TRUE
  AND recorded_at >= NOW() - INTERVAL '24 hours'
ORDER BY triggered_at DESC;
