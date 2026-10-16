-- 008: Unified transaction & account model (Phase 2)
--
-- Adds the canonical double-entry building blocks to every existing profile schema:
--   1. accounts      — wallet/bank/cash/investment buckets (per profile)
--   2. categories    — controlled expense/income category registry
--   3. merchants     — normalized merchant registry (per profile, replaces global
--                      merchant_map.db for new flows)
--   4. transactions  — unified ledger (type/source/confidence/idempotency_key)
--   5. transfer_pairs— double-entry pairing of the two transfer legs
--
-- Also relaxes the legacy duplicate-blocking UNIQUE constraints on
-- {profile}.expenses / {profile}.incomes. Duplicate protection now lives at the
-- idempotency_key level (transactions) instead of silently rejecting legitimate
-- repeat transactions.
--
-- New profiles receive these tables from migrations/005_profile_schema_template.sql
-- (applied at runtime by SchemaInitializer). This migration only reconciles
-- schemas that already exist.

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
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.accounts (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT ''bank'' CHECK (type IN (''bank'',''e-wallet'',''cash'',''investment'',''other'')),
            currency TEXT NOT NULL DEFAULT ''IDR'',
            opening_balance DECIMAL(15, 2) NOT NULL DEFAULT 0,
            is_default BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (name)
        )', s);

        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.categories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT ''expense'' CHECK (kind IN (''expense'',''income'',''transfer'',''investment'',''other'')),
            color TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (name, kind)
        )', s);

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
        )', s, s);

        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.transactions (
            id SERIAL PRIMARY KEY,
            type TEXT NOT NULL CHECK (type IN (''expense'',''income'',''transfer'',''investment'',''adjustment'')),
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
        )', s, s, s, s);

        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_transactions_date ON %I.transactions(tx_date)', s, s);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_transactions_account ON %I.transactions(account_id)', s, s);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_transactions_category ON %I.transactions(category)', s, s);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_transactions_type ON %I.transactions(type)', s, s);

        EXECUTE format('CREATE TABLE IF NOT EXISTS %I.transfer_pairs (
            id SERIAL PRIMARY KEY,
            from_transaction_id INTEGER NOT NULL UNIQUE REFERENCES %I.transactions(id),
            to_transaction_id INTEGER NOT NULL UNIQUE REFERENCES %I.transactions(id),
            amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0),
            pair_key TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )', s, s, s);

        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_transfer_pairs_from ON %I.transfer_pairs(from_transaction_id)', s, s);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_transfer_pairs_to ON %I.transfer_pairs(to_transaction_id)', s, s);

        -- Relax legacy duplicate-blocking unique constraints.
        -- Duplicate protection for new writes is handled by transactions.idempotency_key.
        -- Guard with table existence check (some schemas like 'analytics' don't have these tables).
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = s AND table_name = 'expenses'
        ) THEN
            EXECUTE format('ALTER TABLE %I.expenses DROP CONSTRAINT IF EXISTS expenses_amount_description_category_date_key', s);
        END IF;
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = s AND table_name = 'incomes'
        ) THEN
            EXECUTE format('ALTER TABLE %I.incomes DROP CONSTRAINT IF EXISTS incomes_amount_source_income_type_date_key', s);
        END IF;
    END LOOP;
END $$;
