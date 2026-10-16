-- Profile-scoped composite indexes are managed by SchemaInitializer per profile.

CREATE INDEX IF NOT EXISTS idx_currency_history_composite
    ON public.currency_history(base_currency, target_currency, fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_asset_price_history_composite
    ON public.asset_price_history(asset_symbol, recorded_at DESC);
