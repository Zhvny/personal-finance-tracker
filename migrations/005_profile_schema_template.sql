-- TEMPLATE ONLY — NOT RUN BY RUNNER.
-- This is the authoritative DDL for per-profile schemas.
-- Applied at runtime by SchemaInitializer._ensure_postgres_profile_schema().

CREATE SCHEMA IF NOT EXISTS {PROFILE};

CREATE TABLE IF NOT EXISTS {PROFILE}.expenses (
    id SERIAL PRIMARY KEY,
    amount DECIMAL(15, 2) NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    payment_method TEXT,
    date DATE NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_period TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {PROFILE}.incomes (
    id SERIAL PRIMARY KEY,
    amount DECIMAL(15, 2) NOT NULL,
    source TEXT NOT NULL,
    income_type TEXT NOT NULL,
    date DATE NOT NULL,
    description TEXT,
    is_taxed BOOLEAN DEFAULT FALSE,
    notes TEXT,
    is_recurring BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {PROFILE}.investments (
    id SERIAL PRIMARY KEY,
    asset_type TEXT NOT NULL,
    ticker TEXT NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    remaining_quantity DECIMAL(20, 8) CHECK (remaining_quantity >= 0),
    buy_price DECIMAL(20, 8) NOT NULL CHECK (buy_price >= 0),
    buy_currency TEXT DEFAULT 'IDR',
    buy_date DATE NOT NULL,
    status TEXT DEFAULT 'holding',
    description TEXT,
    is_favorite BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    buy_price_idr DECIMAL(20, 8)
);

CREATE TABLE IF NOT EXISTS {PROFILE}.sell_transactions (
    id SERIAL PRIMARY KEY,
    investment_id INTEGER REFERENCES {PROFILE}.investments(id),
    ticker TEXT NOT NULL,
    sell_date DATE NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    sell_price_usd DECIMAL(20, 8) NOT NULL,
    sell_currency TEXT DEFAULT 'USD',
    fees DECIMAL(20, 2) DEFAULT 0,
    realized_pl_idr DECIMAL(20, 2) NOT NULL,
    realized_pl_pct DECIMAL(10, 4) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sell_price DECIMAL(20, 8),
    realized_pl DECIMAL(20, 2)
);

CREATE TABLE IF NOT EXISTS {PROFILE}.historical_prices (
    id SERIAL PRIMARY KEY,
    investment_id INTEGER REFERENCES {PROFILE}.investments(id),
    snapshot_date DATE NOT NULL,
    price_usd DECIMAL(20, 8) NOT NULL,
    price_idr DECIMAL(20, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (investment_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS {PROFILE}.recurrence_candidates (
    id SERIAL PRIMARY KEY,
    description TEXT NOT NULL UNIQUE,
    category TEXT,
    amount DECIMAL(15, 2),
    avg_amount REAL,
    interval_days INTEGER,
    occurrences INTEGER,
    confidence DECIMAL(5, 4),
    last_seen DATE,
    status TEXT DEFAULT 'pending',
    is_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {PROFILE}.user_stats (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {PROFILE}.fx_rates (
    pair TEXT NOT NULL,
    rate_date DATE NOT NULL,
    rate DECIMAL(20, 8) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pair, rate_date)
);

CREATE TABLE IF NOT EXISTS {PROFILE}.manual_balances (
    key TEXT PRIMARY KEY,
    value DECIMAL(15, 2) NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {PROFILE}.cash_split (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    physical_cash DECIMAL(15, 2) NOT NULL DEFAULT 0,
    bank_savings DECIMAL(15, 2) NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {PROFILE}.transfer_log (
    id SERIAL PRIMARY KEY,
    direction TEXT NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {PROFILE}.behavioral_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE,
    data_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {PROFILE}.networth_snapshots (
    date DATE PRIMARY KEY,
    total_networth DECIMAL(15, 2) NOT NULL,
    cash DECIMAL(15, 2),
    bank_savings DECIMAL(15, 2),
    emergency_fund DECIMAL(15, 2),
    crypto DECIMAL(15, 2),
    stocks DECIMAL(15, 2),
    gold DECIMAL(15, 2),
    other_assets DECIMAL(15, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {PROFILE}.budgets (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    limit_amt DECIMAL(15, 2) NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    UNIQUE (category, year, month)
);

CREATE TABLE IF NOT EXISTS {PROFILE}.goals (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    target_amount DECIMAL(15, 2) NOT NULL,
    current_amount DECIMAL(15, 2) DEFAULT 0,
    target_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {PROFILE}.stock_favorites (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    is_favorite BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS {PROFILE}.virtual_accounts (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    parent_account_id INTEGER,
    balance DECIMAL(15, 2) DEFAULT 0,
    target_amount DECIMAL(15, 2) DEFAULT 0,
    currency VARCHAR(10) DEFAULT 'USD',
    profile_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {PROFILE}.reward_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    state_json JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Phase 2: Unified transaction & account model ─────────────────────────────

CREATE TABLE IF NOT EXISTS {PROFILE}.accounts (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'bank' CHECK (type IN ('bank', 'e-wallet', 'cash', 'investment', 'other')),
    currency TEXT NOT NULL DEFAULT 'IDR',
    opening_balance DECIMAL(15, 2) NOT NULL DEFAULT 0,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS {PROFILE}.categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'expense' CHECK (kind IN ('expense', 'income', 'transfer', 'investment', 'other')),
    color TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name, kind)
);

CREATE TABLE IF NOT EXISTS {PROFILE}.merchants (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT,
    category_id INTEGER REFERENCES {PROFILE}.categories(id),
    category TEXT,
    edit_count INTEGER NOT NULL DEFAULT 1,
    last_seen DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS {PROFILE}.transactions (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('expense', 'income', 'transfer', 'investment', 'adjustment')),
    amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'IDR',
    account_id INTEGER REFERENCES {PROFILE}.accounts(id),
    merchant_id INTEGER REFERENCES {PROFILE}.merchants(id),
    category_id INTEGER REFERENCES {PROFILE}.categories(id),
    category TEXT,
    description TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    confidence DECIMAL(5, 4),
    idempotency_key TEXT UNIQUE,
    tx_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_{PROFILE}_transactions_date ON {PROFILE}.transactions(tx_date);
CREATE INDEX IF NOT EXISTS idx_{PROFILE}_transactions_account ON {PROFILE}.transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_{PROFILE}_transactions_category ON {PROFILE}.transactions(category);
CREATE INDEX IF NOT EXISTS idx_{PROFILE}_transactions_type ON {PROFILE}.transactions(type);

CREATE TABLE IF NOT EXISTS {PROFILE}.transfer_pairs (
    id SERIAL PRIMARY KEY,
    from_transaction_id INTEGER NOT NULL UNIQUE REFERENCES {PROFILE}.transactions(id),
    to_transaction_id INTEGER NOT NULL UNIQUE REFERENCES {PROFILE}.transactions(id),
    amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0),
    pair_key TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_{PROFILE}_transfer_pairs_from ON {PROFILE}.transfer_pairs(from_transaction_id);
CREATE INDEX IF NOT EXISTS idx_{PROFILE}_transfer_pairs_to ON {PROFILE}.transfer_pairs(to_transaction_id);
