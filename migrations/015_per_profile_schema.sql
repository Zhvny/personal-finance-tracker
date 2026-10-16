-- 015_per_profile_schema.sql
-- Per-profile schemas: 'personal' and 'business' (default profiles).
-- Custom profiles added later via API + dynamic provisioning (see Phase B3).
--
-- This migration is idempotent (CREATE TABLE IF NOT EXISTS) so re-running is safe.
-- Tables follow the same DDL as 005_profile_schema_template.sql but rendered
-- via format() inside a DO block to avoid needing {PROFILE} placeholder support
-- in the migration runner.

DO $$
DECLARE
    profile_name TEXT;
    profile_names TEXT[] := ARRAY['personal', 'business'];
BEGIN
    FOREACH profile_name IN ARRAY profile_names
    LOOP
        EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', profile_name);

        -- expenses
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.expenses (
            id SERIAL PRIMARY KEY,
            amount DECIMAL(15, 2) NOT NULL,
            description TEXT,
            category TEXT NOT NULL,
            payment_method TEXT,
            date DATE NOT NULL,
            is_recurring BOOLEAN DEFAULT FALSE,
            recurring_period TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )', profile_name);

        -- incomes
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.incomes (
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
        )', profile_name);

        -- investments
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.investments (
            id SERIAL PRIMARY KEY,
            asset_type TEXT NOT NULL,
            ticker TEXT NOT NULL,
            quantity DECIMAL(20, 8) NOT NULL,
            remaining_quantity DECIMAL(20, 8) CHECK (remaining_quantity >= 0),
            buy_price DECIMAL(20, 8) NOT NULL CHECK (buy_price >= 0),
            buy_currency TEXT DEFAULT ''IDR'',
            buy_date DATE NOT NULL,
            status TEXT DEFAULT ''holding'',
            description TEXT,
            is_favorite BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            buy_price_idr DECIMAL(20, 8)
        )', profile_name);

        -- sell_transactions
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.sell_transactions (
            id SERIAL PRIMARY KEY,
            investment_id INTEGER REFERENCES %I.investments(id),
            ticker TEXT NOT NULL,
            sell_date DATE NOT NULL,
            quantity DECIMAL(20, 8) NOT NULL,
            sell_price_usd DECIMAL(20, 8) NOT NULL,
            sell_currency TEXT DEFAULT ''USD'',
            fees DECIMAL(20, 2) DEFAULT 0,
            realized_pl_idr DECIMAL(20, 2) NOT NULL,
            realized_pl_pct DECIMAL(10, 4) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sell_price DECIMAL(20, 8),
            realized_pl DECIMAL(20, 2)
        )', profile_name, profile_name);

        -- historical_prices
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.historical_prices (
            id SERIAL PRIMARY KEY,
            investment_id INTEGER REFERENCES %I.investments(id),
            snapshot_date DATE NOT NULL,
            price_usd DECIMAL(20, 8) NOT NULL,
            price_idr DECIMAL(20, 2) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (investment_id, snapshot_date)
        )', profile_name, profile_name);

        -- recurrence_candidates
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.recurrence_candidates (
            id SERIAL PRIMARY KEY,
            amount DECIMAL(15, 2),
            description TEXT,
            category TEXT,
            interval_days INTEGER,
            occurrences INTEGER,
            confidence DECIMAL(5, 4),
            last_seen DATE,
            status TEXT DEFAULT ''pending'',
            is_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )', profile_name);

        -- user_stats
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.user_stats (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )', profile_name);

        -- fx_rates
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.fx_rates (
            pair TEXT NOT NULL,
            rate_date DATE NOT NULL,
            rate DECIMAL(20, 8) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (pair, rate_date)
        )', profile_name);

        -- manual_balances
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.manual_balances (
            key TEXT PRIMARY KEY,
            value DECIMAL(15, 2) NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )', profile_name);

        -- cash_split
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.cash_split (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            physical_cash DECIMAL(15, 2) NOT NULL DEFAULT 0,
            bank_savings DECIMAL(15, 2) NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )', profile_name);

        -- transfer_log
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.transfer_log (
            id SERIAL PRIMARY KEY,
            direction TEXT NOT NULL,
            amount DECIMAL(15, 2) NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )', profile_name);

        -- behavioral_snapshots
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.behavioral_snapshots (
            snapshot_date DATE,
            data_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )', profile_name);

        -- networth_snapshots
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.networth_snapshots (
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
        )', profile_name);

        -- budgets
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.budgets (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL,
            limit_amt DECIMAL(15, 2) NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            UNIQUE (category, year, month)
        )', profile_name);

        -- goals
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.goals (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            target_amount DECIMAL(15, 2) NOT NULL,
            current_amount DECIMAL(15, 2) DEFAULT 0,
            target_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )', profile_name);

        -- stock_favorites
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.stock_favorites (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            is_favorite BOOLEAN DEFAULT TRUE
        )', profile_name);

        -- virtual_accounts
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.virtual_accounts (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            parent_account_id INTEGER,
            balance DECIMAL(15, 2) DEFAULT 0,
            target_amount DECIMAL(15, 2) DEFAULT 0,
            currency VARCHAR(10) DEFAULT ''USD'',
            profile_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )', profile_name);

        -- reward_state
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.reward_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state_json JSONB NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )', profile_name);

        -- accounts (Phase 2 unified model)
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.accounts (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT ''bank'' CHECK (type IN (''bank'', ''e-wallet'', ''cash'', ''investment'', ''other'')),
            currency TEXT NOT NULL DEFAULT ''IDR'',
            opening_balance DECIMAL(15, 2) NOT NULL DEFAULT 0,
            is_default BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (name)
        )', profile_name);

        -- categories
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.categories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT ''expense'' CHECK (kind IN (''expense'', ''income'', ''transfer'', ''investment'', ''other'')),
            color TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (name, kind)
        )', profile_name);

        -- merchants
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.merchants (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT,
            category_id INTEGER REFERENCES %I.categories(id),
            category TEXT,
            edit_count INTEGER NOT NULL DEFAULT 1,
            last_seen DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (name)
        )', profile_name, profile_name);

        -- transactions (Phase 2 unified)
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.transactions (
            id SERIAL PRIMARY KEY,
            type TEXT NOT NULL CHECK (type IN (''expense'', ''income'', ''transfer'', ''investment'', ''adjustment'')),
            amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0),
            currency TEXT NOT NULL DEFAULT ''IDR'',
            account_id INTEGER REFERENCES %I.accounts(id),
            merchant_id INTEGER REFERENCES %I.merchants(id),
            category_id INTEGER REFERENCES %I.categories(id),
            category TEXT,
            description TEXT,
            source TEXT NOT NULL DEFAULT ''manual'',
            confidence DECIMAL(5, 4),
            idempotency_key TEXT UNIQUE,
            tx_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )', profile_name, profile_name, profile_name, profile_name);

        -- transfer_pairs
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.transfer_pairs (
            id SERIAL PRIMARY KEY,
            from_transaction_id INTEGER NOT NULL UNIQUE REFERENCES %I.transactions(id),
            to_transaction_id INTEGER NOT NULL UNIQUE REFERENCES %I.transactions(id),
            amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0),
            pair_key TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )', profile_name, profile_name, profile_name);

        -- Indexes
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_expenses_date ON %I.expenses(date)', profile_name, profile_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_incomes_date ON %I.incomes(date)', profile_name, profile_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_investments_ticker ON %I.investments(ticker)', profile_name, profile_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_va_profile ON %I.virtual_accounts(profile_id)', profile_name, profile_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_transactions_date ON %I.transactions(tx_date)', profile_name, profile_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_transactions_account ON %I.transactions(account_id)', profile_name, profile_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_transactions_category ON %I.transactions(category)', profile_name, profile_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_transactions_type ON %I.transactions(type)', profile_name, profile_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_transfer_pairs_from ON %I.transfer_pairs(from_transaction_id)', profile_name, profile_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_transfer_pairs_to ON %I.transfer_pairs(to_transaction_id)', profile_name, profile_name);

        -- Default rows
        EXECUTE format('INSERT INTO %I.user_stats (key, value) VALUES (''lust_points'', ''100'') ON CONFLICT (key) DO NOTHING', profile_name);
        EXECUTE format('INSERT INTO %I.cash_split (id, physical_cash, bank_savings) VALUES (1, 0, 0) ON CONFLICT (id) DO NOTHING', profile_name);
    END LOOP;
END $$;
