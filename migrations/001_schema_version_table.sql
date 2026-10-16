-- Migration 001: Create schema version tracking table
-- Applied by: migrations/runner.py
-- This MUST be the first migration. It bootstraps the version tracking.

CREATE SCHEMA IF NOT EXISTS public;

CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    description TEXT,
    checksum VARCHAR(64)
);

CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.audit_log (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action TEXT NOT NULL,
    module TEXT,
    details TEXT,
    ip TEXT,
    method TEXT,
    path TEXT,
    scope TEXT,
    status_code INTEGER,
    latency_ms REAL,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit.audit_log(ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_module ON audit.audit_log(module);

CREATE SCHEMA IF NOT EXISTS system;

CREATE TABLE IF NOT EXISTS system.profiles (
    id TEXT PRIMARY KEY,
    display_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    meta JSONB DEFAULT '{}'
);
