CREATE SCHEMA IF NOT EXISTS market;

CREATE TABLE IF NOT EXISTS market.covariance_cache (
    id SERIAL PRIMARY KEY,
    hash_key TEXT UNIQUE NOT NULL,
    matrix_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_covariance_hash ON market.covariance_cache(hash_key);

CREATE TABLE IF NOT EXISTS market.market_data (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    open NUMERIC(20, 8),
    high NUMERIC(20, 8),
    low NUMERIC(20, 8),
    close NUMERIC(20, 8),
    volume NUMERIC(20, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_market_data_ticker_date ON market.market_data(ticker, date DESC);

CREATE TABLE IF NOT EXISTS market.ohlcv_data (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    date TIMESTAMP NOT NULL,
    open NUMERIC(20, 8),
    high NUMERIC(20, 8),
    low NUMERIC(20, 8),
    close NUMERIC(20, 8),
    volume NUMERIC(20, 8),
    timeframe TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date, timeframe)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_data_ticker_date ON market.ohlcv_data(ticker, date DESC);
