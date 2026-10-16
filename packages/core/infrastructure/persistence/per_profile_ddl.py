"""
Per-profile DDL generator.

Single source of truth for the 23 tables each profile schema needs.
Used by:
  - SchemaInitializer.provision_profile_schema (B1, runtime)
  - migrations/015_per_profile_schema.sql (A1, deployment)

The DDL is also embedded verbatim in 015_per_profile_schema.sql so the
migration runner can apply it without Python at deploy time. If you add a
table here, also update 015_per_profile_schema.sql.

Profile name is validated by the caller (regex `[a-zA-Z0-9_]+`) before
interpolation here, so format() is safe from SQL injection.
"""
from typing import List

# 23 tables per profile schema (kept in sync with migration 015).
_TABLE_COUNT = 23


def _q(value: str) -> str:
    """SQL string literal with single-quote escaping."""
    return "'" + value.replace("'", "''") + "'"


def build_all_ddl_for_profile(profile: str) -> List[str]:
    """
    Return all DDL statements to create a profile schema + its 23 tables +
    indexes + default seed rows. Idempotent (every statement uses
    CREATE TABLE/INDEX IF NOT EXISTS and INSERT ... ON CONFLICT DO NOTHING).

    Args:
        profile: Profile name. Caller MUST have validated against
                 `^[a-zA-Z0-9_]+$` (SchemaInitializer and migration 015 do this).

    Returns:
        List of SQL statements in dependency order.
    """
    p = profile
    p_lit = _q(profile)
    stmts: List[str] = []

    # Schema
    stmts.append(f"CREATE SCHEMA IF NOT EXISTS {p}")

    # 23 tables (all in dependency order: referenced tables before referencing)
    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.expenses (
        id SERIAL PRIMARY KEY,
        amount DECIMAL(15, 2) NOT NULL,
        description TEXT,
        category TEXT NOT NULL,
        payment_method TEXT,
        date DATE NOT NULL,
        is_recurring BOOLEAN DEFAULT FALSE,
        recurring_period TEXT,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.incomes (
        id SERIAL PRIMARY KEY,
        amount DECIMAL(15, 2) NOT NULL,
        source TEXT NOT NULL,
        income_type TEXT NOT NULL,
        date DATE NOT NULL,
        description TEXT,
        is_taxed BOOLEAN DEFAULT FALSE,
        notes TEXT,
        is_recurring BOOLEAN DEFAULT FALSE,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.investments (
        id SERIAL PRIMARY KEY,
        asset_type TEXT NOT NULL,
        ticker TEXT NOT NULL,
        quantity DECIMAL(20, 8) NOT NULL,
        remaining_quantity DECIMAL(20, 8) CHECK (remaining_quantity >= 0),
        buy_price DECIMAL(20, 8) NOT NULL CHECK (buy_price >= 0),
        buy_currency TEXT DEFAULT {_q('IDR')},
        buy_date DATE NOT NULL,
        status TEXT DEFAULT {_q('holding')},
        description TEXT,
        is_favorite BOOLEAN DEFAULT FALSE,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        buy_price_idr DECIMAL(20, 8)
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.sell_transactions (
        id SERIAL PRIMARY KEY,
        investment_id INTEGER REFERENCES {p}.investments(id),
        ticker TEXT NOT NULL,
        sell_date DATE NOT NULL,
        quantity DECIMAL(20, 8) NOT NULL,
        sell_price_usd DECIMAL(20, 8) NOT NULL,
        sell_currency TEXT DEFAULT {_q('USD')},
        fees DECIMAL(20, 2) DEFAULT 0,
        realized_pl_idr DECIMAL(20, 2) NOT NULL,
        realized_pl_pct DECIMAL(10, 4) NOT NULL,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        sell_price DECIMAL(20, 8),
        realized_pl DECIMAL(20, 2)
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.historical_prices (
        id SERIAL PRIMARY KEY,
        investment_id INTEGER REFERENCES {p}.investments(id),
        snapshot_date DATE NOT NULL,
        price_usd DECIMAL(20, 8) NOT NULL,
        price_idr DECIMAL(20, 2) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER,
        UNIQUE (investment_id, snapshot_date)
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.recurrence_candidates (
        id SERIAL PRIMARY KEY,
        amount DECIMAL(15, 2),
        description TEXT,
        category TEXT,
        interval_days INTEGER,
        occurrences INTEGER,
        confidence DECIMAL(5, 4),
        last_seen DATE,
        status TEXT DEFAULT {_q('pending')},
        is_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
        updated_at TEXT,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.user_stats (
        key TEXT PRIMARY KEY,
        value TEXT,
        user_id INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.fx_rates (
        pair TEXT NOT NULL,
        rate_date DATE NOT NULL,
        rate DECIMAL(20, 8) NOT NULL,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (pair, rate_date)
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.manual_balances (
        key TEXT PRIMARY KEY,
        value DECIMAL(15, 2) NOT NULL DEFAULT 0,
        user_id INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.cash_split (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        physical_cash DECIMAL(15, 2) NOT NULL DEFAULT 0,
        bank_savings DECIMAL(15, 2) NOT NULL DEFAULT 0,
        user_id INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.transfer_log (
        id SERIAL PRIMARY KEY,
        direction TEXT NOT NULL,
        amount DECIMAL(15, 2) NOT NULL,
        note TEXT,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.behavioral_snapshots (
        snapshot_date DATE,
        data_json TEXT NOT NULL,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.networth_snapshots (
        date DATE PRIMARY KEY,
        total_networth DECIMAL(15, 2) NOT NULL,
        cash DECIMAL(15, 2),
        bank_savings DECIMAL(15, 2),
        emergency_fund DECIMAL(15, 2),
        crypto DECIMAL(15, 2),
        stocks DECIMAL(15, 2),
        gold DECIMAL(15, 2),
        other_assets DECIMAL(15, 2),
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.budgets (
        id SERIAL PRIMARY KEY,
        category TEXT NOT NULL,
        limit_amt DECIMAL(15, 2) NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        user_id INTEGER,
        UNIQUE (category, year, month)
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.goals (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        target_amount DECIMAL(15, 2) NOT NULL,
        current_amount DECIMAL(15, 2) DEFAULT 0,
        target_date DATE,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.stock_favorites (
        id SERIAL PRIMARY KEY,
        ticker VARCHAR(20) NOT NULL,
        user_id INTEGER,
        is_favorite BOOLEAN DEFAULT TRUE
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.virtual_accounts (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        parent_account_id INTEGER,
        balance DECIMAL(15, 2) DEFAULT 0,
        target_amount DECIMAL(15, 2) DEFAULT 0,
        currency VARCHAR(10) DEFAULT {_q('USD')},
        profile_id TEXT NOT NULL,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.reward_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        state_json JSONB NOT NULL,
        user_id INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.accounts (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT {_q('bank')} CHECK (type IN ({_q('bank')}, {_q('e-wallet')}, {_q('cash')}, {_q('investment')}, {_q('other')})),
        currency TEXT NOT NULL DEFAULT {_q('IDR')},
        opening_balance DECIMAL(15, 2) NOT NULL DEFAULT 0,
        is_default BOOLEAN NOT NULL DEFAULT FALSE,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (name)
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.categories (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT {_q('expense')} CHECK (kind IN ({_q('expense')}, {_q('income')}, {_q('transfer')}, {_q('investment')}, {_q('other')})),
        color TEXT,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (name, kind)
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.merchants (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        display_name TEXT,
        category_id INTEGER REFERENCES {p}.categories(id),
        category TEXT,
        edit_count INTEGER NOT NULL DEFAULT 1,
        last_seen DATE,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (name)
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.transactions (
        id SERIAL PRIMARY KEY,
        type TEXT NOT NULL CHECK (type IN ({_q('expense')}, {_q('income')}, {_q('transfer')}, {_q('investment')}, {_q('adjustment')})),
        amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0),
        currency TEXT NOT NULL DEFAULT {_q('IDR')},
        account_id INTEGER REFERENCES {p}.accounts(id),
        merchant_id INTEGER REFERENCES {p}.merchants(id),
        category_id INTEGER REFERENCES {p}.categories(id),
        category TEXT,
        description TEXT,
        source TEXT NOT NULL DEFAULT {_q('manual')},
        confidence DECIMAL(5, 4),
        idempotency_key TEXT UNIQUE,
        tx_date DATE NOT NULL,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    stmts.append(f"""CREATE TABLE IF NOT EXISTS {p}.transfer_pairs (
        id SERIAL PRIMARY KEY,
        from_transaction_id INTEGER NOT NULL UNIQUE REFERENCES {p}.transactions(id),
        to_transaction_id INTEGER NOT NULL UNIQUE REFERENCES {p}.transactions(id),
        amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0),
        pair_key TEXT NOT NULL UNIQUE,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Indexes
    stmts.append(f"CREATE INDEX IF NOT EXISTS idx_{p}_expenses_date ON {p}.expenses(date)")
    stmts.append(f"CREATE INDEX IF NOT EXISTS idx_{p}_incomes_date ON {p}.incomes(date)")
    stmts.append(f"CREATE INDEX IF NOT EXISTS idx_{p}_investments_ticker ON {p}.investments(ticker)")
    stmts.append(f"CREATE INDEX IF NOT EXISTS idx_{p}_va_profile ON {p}.virtual_accounts(profile_id)")
    stmts.append(f"CREATE INDEX IF NOT EXISTS idx_{p}_transactions_date ON {p}.transactions(tx_date)")
    stmts.append(f"CREATE INDEX IF NOT EXISTS idx_{p}_transactions_account ON {p}.transactions(account_id)")
    stmts.append(f"CREATE INDEX IF NOT EXISTS idx_{p}_transactions_category ON {p}.transactions(category)")
    stmts.append(f"CREATE INDEX IF NOT EXISTS idx_{p}_transactions_type ON {p}.transactions(type)")
    stmts.append(f"CREATE INDEX IF NOT EXISTS idx_{p}_transfer_pairs_from ON {p}.transfer_pairs(from_transaction_id)")
    stmts.append(f"CREATE INDEX IF NOT EXISTS idx_{p}_transfer_pairs_to ON {p}.transfer_pairs(to_transaction_id)")

    # Default seed rows
    stmts.append(
        f"INSERT INTO {p}.user_stats (key, value) VALUES ({_q('lust_points')}, {_q('100')}) "
        f"ON CONFLICT (key) DO NOTHING"
    )
    stmts.append(
        f"INSERT INTO {p}.cash_split (id, physical_cash, bank_savings) VALUES (1, 0, 0) "
        f"ON CONFLICT (id) DO NOTHING"
    )
    stmts.append(
        f"INSERT INTO {p}.accounts (name, type, currency, opening_balance, is_default) "
        f"SELECT {_q('Default')}, {_q('bank')}, {_q('IDR')}, 0, TRUE "
        f"WHERE NOT EXISTS (SELECT 1 FROM {p}.accounts)"
    )
    # Default categories
    default_categories = [
        ("Food", "expense"), ("Transport", "expense"), ("Housing", "expense"),
        ("Entertainment", "expense"), ("Health", "expense"), ("Shopping", "expense"),
        ("Education", "expense"), ("Investment", "expense"), ("Other", "expense"),
        ("Salary", "income"), ("Bonus", "income"), ("Gift", "income"), ("Other", "income"),
    ]
    for cat_name, cat_kind in default_categories:
        stmts.append(
            f"INSERT INTO {p}.categories (name, kind) VALUES ({_q(cat_name)}, {_q(cat_kind)}) "
            f"ON CONFLICT (name, kind) DO NOTHING"
        )

    return stmts


def expected_table_count() -> int:
    """Return the expected number of tables per profile schema."""
    return _TABLE_COUNT
