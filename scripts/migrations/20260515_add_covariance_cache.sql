-- Migration: Add Covariance Cache Table
-- Date: 2026-05-15

CREATE TABLE IF NOT EXISTS market.covariance_cache (
    id SERIAL PRIMARY KEY,
    hash_key TEXT UNIQUE NOT NULL,
    matrix_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_covariance_hash ON market.covariance_cache(hash_key);

-- Log migration
INSERT INTO audit.audit_log (action, module, details)
VALUES ('MIGRATION', 'DATABASE', 'Created market.covariance_cache table');
