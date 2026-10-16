import logging

import psycopg2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_database():
    conn_params = {
        "dbname": "finance_tracker",
        "user": "postgres",
        "password": "postgres",
        "host": "localhost",
        "port": "5432"
    }

    try:
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True
        cur = conn.cursor()

        # 1. Create Schemas
        logger.info("Creating schemas...")
        cur.execute("CREATE SCHEMA IF NOT EXISTS financials;")
        cur.execute("CREATE SCHEMA IF NOT EXISTS market;")
        cur.execute("CREATE SCHEMA IF NOT EXISTS core;")
        cur.execute("CREATE SCHEMA IF NOT EXISTS investment;")
        cur.execute("CREATE SCHEMA IF NOT EXISTS audit;")
        cur.execute("CREATE SCHEMA IF NOT EXISTS system;")

        # 2. Financials Tables
        logger.info("Creating financials tables...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS financials.expenses (
                id SERIAL PRIMARY KEY,
                amount DECIMAL(15, 2) NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                payment_method TEXT,
                date DATE NOT NULL,
                is_recurring BOOLEAN DEFAULT FALSE,
                recurring_period TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (amount, description, category, date)
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS financials.incomes (
                id SERIAL PRIMARY KEY,
                amount DECIMAL(15, 2) NOT NULL,
                source TEXT NOT NULL,
                income_type TEXT NOT NULL,
                date DATE NOT NULL,
                description TEXT,
                is_taxed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (amount, source, income_type, date)
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS financials.budgets (
                id SERIAL PRIMARY KEY,
                category TEXT NOT NULL,
                limit_amt DECIMAL(15, 2) NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                UNIQUE (category, year, month)
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS financials.recurrence_candidates (
                id SERIAL PRIMARY KEY,
                amount DECIMAL(15, 2) NOT NULL,
                description TEXT,
                category TEXT,
                interval_days INTEGER,
                confidence DECIMAL(5, 4),
                last_seen DATE,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Core Tables (Balances, Goals, Behavioral)
        logger.info("Creating core tables...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS core.manual_balances (
                key TEXT PRIMARY KEY,
                value DECIMAL(15, 2) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS core.cash_split (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                physical_cash DECIMAL(15, 2) NOT NULL DEFAULT 0,
                bank_savings DECIMAL(15, 2) NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS core.transfer_log (
                id SERIAL PRIMARY KEY,
                direction TEXT NOT NULL,
                amount DECIMAL(15, 2) NOT NULL,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS core.goals (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                target_amount DECIMAL(15, 2) NOT NULL,
                current_amount DECIMAL(15, 2) DEFAULT 0,
                target_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS core.behavioral_snapshots (
                id SERIAL PRIMARY KEY,
                snapshot_date DATE,
                data_json JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS core.reward_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                state_json JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS core.networth_snapshots (
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
        """)

        # 4. Investment Tables
        logger.info("Creating investment tables...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS investment.investments (
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS investment.sell_transactions (
                id SERIAL PRIMARY KEY,
                investment_id INTEGER REFERENCES investment.investments(id),
                ticker TEXT NOT NULL,
                sell_date DATE NOT NULL,
                quantity DECIMAL(20, 8) NOT NULL,
                sell_price_usd DECIMAL(20, 8) NOT NULL,
                sell_currency TEXT DEFAULT 'USD',
                fees DECIMAL(20, 2) DEFAULT 0,
                realized_pl_idr DECIMAL(20, 2) NOT NULL,
                realized_pl_pct DECIMAL(10, 4) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS investment.historical_prices (
                id SERIAL PRIMARY KEY,
                investment_id INTEGER REFERENCES investment.investments(id),
                snapshot_date DATE NOT NULL,
                price_usd DECIMAL(20, 8) NOT NULL,
                price_idr DECIMAL(20, 2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (investment_id, snapshot_date)
            );
        """)


        cur.execute("""
            CREATE TABLE IF NOT EXISTS investment.fx_rates (
                pair TEXT NOT NULL,
                rate_date DATE NOT NULL,
                rate DECIMAL(20, 8) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (pair, rate_date)
            );
        """)

        # 5. Market Tables
        logger.info("Creating market tables...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS market.ohlcv_cache (
                ticker TEXT NOT NULL,
                period TEXT NOT NULL,
                fetched_at TIMESTAMP NOT NULL,
                data BYTEA NOT NULL,
                PRIMARY KEY (ticker, period)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS market.covariance_cache (
                id SERIAL PRIMARY KEY,
                hash_key TEXT UNIQUE NOT NULL,
                matrix_data JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_covariance_hash ON market.covariance_cache(hash_key);
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS market.latest_prices (
                ticker TEXT PRIMARY KEY,
                price DECIMAL(20, 8) NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                change_pct DECIMAL(10, 4),
                volume BIGINT,
                metadata TEXT
            );
        """)

        # 6. Audit Tables
        logger.info("Creating audit tables...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit.audit_log (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action TEXT,
                module TEXT,
                details TEXT,
                user_id TEXT
            );
        """)

        # 7. System Tables
        logger.info("Creating system tables...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS system.maintenance_status (
                service_name TEXT PRIMARY KEY,
                status TEXT DEFAULT 'OK',
                last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 8. Optimization: Indexes
        logger.info("Creating indexes...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON financials.expenses(date);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_incomes_date ON financials.incomes(date);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_fetched ON market.ohlcv_cache(fetched_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_investments_ticker ON investment.investments(ticker);")

        logger.info("PostgreSQL setup complete!")
        cur.close()
        conn.close()

    except Exception as e:
        logger.error(f"Failed to setup PostgreSQL: {e}")
        raise

if __name__ == "__main__":
    setup_database()
