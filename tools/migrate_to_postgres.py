import re
import sqlite3
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2 import extras

# Identifiers (schema/table names) cannot be passed as bound parameters, so any
# dynamic identifier MUST be validated against this allowlist pattern before being
# interpolated into SQL. This prevents SQL injection via table/schema names.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _valid_identifier(name: str) -> bool:
    return bool(_IDENT_RE.match(name or ""))

# Configuration
POSTGRES_CONFIG = {
    "dbname": "finance_tracker",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

ROOT = Path(__file__).parent.parent.resolve()

SOURCES = {
    "expense": [ROOT / "apps" / "cli" / "expense_tracker" / "data" / "expense.db"],
    "income": [ROOT / "apps" / "cli" / "income_tracker" / "data" / "income.db"],
    "portfolio": [ROOT / "apps" / "cli" / "investment_tracker" / "data" / "portfolio.db", ROOT / "finance-tracker-gui" / "data" / "portfolio.db"],
    "goals": [ROOT / "data" / "goals.db", ROOT / "finance-tracker-gui" / "data" / "goals.db", ROOT / "apps" / "cli" / "advanced_features" / "data" / "goals.db"],
    "budget": [ROOT / "data" / "budget.db", ROOT / "finance-tracker-gui" / "data" / "budget.db", ROOT / "apps" / "cli" / "advanced_features" / "data" / "budget.db"],
    "market": [ROOT / "finance-tracker-gui" / "data" / "market.db"],
    "audit_log": [ROOT / "finance-tracker-gui" / "data" / "audit_log.db"],
    "merchant": [ROOT / "finance-tracker-gui" / "data" / "merchant_map.db"],
    "networth": [ROOT / "finance-tracker-gui" / "data" / "networth_history.db"],
    "preferences": [ROOT / "data" / "goals.db", ROOT / "finance-tracker-gui" / "data" / "goals.db"]
}

def get_pg_conn():
    return psycopg2.connect(**POSTGRES_CONFIG)

def table_exists(sl_conn, table_name):
    cur = sl_conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cur.fetchone() is not None

def init_db():
    print("Resetting and Ensuring PostgreSQL Schema (Sync with Repositories)...")
    conn = get_pg_conn()
    cur = conn.cursor()

    # 1. Ensure schemas exist
    for s in ["core", "investment", "market", "audit", "financials"]:
        if not _valid_identifier(s):
            raise ValueError(f"Invalid schema name refused: {s!r}")
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")

    # 2. Recreate tables to match Repositories and Fix constraints
    cur.execute("DROP TABLE IF EXISTS investment.sell_transactions CASCADE")
    cur.execute("DROP TABLE IF EXISTS investment.historical_prices CASCADE")
    cur.execute("DROP TABLE IF EXISTS investment.investments CASCADE")
    cur.execute("DROP TABLE IF EXISTS investment.user_stats CASCADE")
    cur.execute("DROP TABLE IF EXISTS financials.expenses CASCADE")
    cur.execute("DROP TABLE IF EXISTS financials.incomes CASCADE")
    cur.execute("DROP TABLE IF EXISTS financials.income CASCADE") # Old singular name
    cur.execute("DROP TABLE IF EXISTS financials.budgets CASCADE")
    cur.execute("DROP TABLE IF EXISTS financials.recurrence_candidates CASCADE")
    cur.execute("DROP TABLE IF EXISTS core.goals CASCADE")
    cur.execute("DROP TABLE IF EXISTS core.merchant_map CASCADE")
    cur.execute("DROP TABLE IF EXISTS core.networth_snapshots CASCADE")
    cur.execute("DROP TABLE IF EXISTS core.manual_balances CASCADE")
    cur.execute("DROP TABLE IF EXISTS core.cash_split CASCADE")
    cur.execute("DROP TABLE IF EXISTS core.transfer_log CASCADE")
    cur.execute("DROP TABLE IF EXISTS core.reward_state CASCADE")
    cur.execute("DROP TABLE IF EXISTS core.behavioral_snapshots CASCADE")
    cur.execute("DROP TABLE IF EXISTS core.settings CASCADE")
    cur.execute("DROP TABLE IF EXISTS core.preferences CASCADE")
    cur.execute("DROP TABLE IF EXISTS audit.audit_log CASCADE")
    cur.execute("DROP TABLE IF EXISTS audit.predictions_audit CASCADE")
    cur.execute("DROP TABLE IF EXISTS audit.export_log CASCADE")

    cur.execute("""
        CREATE TABLE financials.expenses (
            id SERIAL PRIMARY KEY, amount DECIMAL(15,2), description TEXT, 
            category TEXT, payment_method TEXT, date DATE, 
            is_recurring BOOLEAN DEFAULT FALSE, recurring_period TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(amount, description, category, date)
        );
        
        CREATE TABLE financials.incomes (
            id SERIAL PRIMARY KEY, amount DECIMAL(15,2), source TEXT, 
            income_type TEXT, date DATE, description TEXT, 
            is_taxed BOOLEAN DEFAULT FALSE, notes TEXT, is_recurring BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(amount, source, date)
        );
        
        CREATE TABLE financials.budgets (
            id SERIAL PRIMARY KEY, category TEXT, limit_amt DECIMAL(15,2), 
            year INTEGER, month INTEGER,
            UNIQUE(category, year, month)
        );

        CREATE TABLE financials.recurrence_candidates (
            id SERIAL PRIMARY KEY, amount DECIMAL(15,2), description TEXT,
            category TEXT, interval_days INTEGER, confidence DECIMAL(5,4),
            last_seen DATE, status TEXT DEFAULT 'pending'
        );
        
        CREATE TABLE core.goals (
            id SERIAL PRIMARY KEY, name TEXT UNIQUE, target_amount DECIMAL(15,2), 
            current_amount DECIMAL(15,2), target_date DATE
        );
        
        CREATE TABLE investment.investments (
            id SERIAL PRIMARY KEY, asset_type TEXT, ticker TEXT, 
            quantity DECIMAL(20,8), buy_price DECIMAL(20,8), buy_currency TEXT, 
            buy_date DATE, status TEXT, remaining_quantity DECIMAL(20,8),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_favorite BOOLEAN DEFAULT FALSE
        );

        CREATE TABLE investment.sell_transactions (
            id SERIAL PRIMARY KEY, investment_id INTEGER REFERENCES investment.investments(id),
            ticker TEXT, sell_date DATE, quantity DECIMAL(20, 8),
            sell_price_usd DECIMAL(20, 8), sell_currency TEXT, fees DECIMAL(20, 2),
            realized_pl_idr DECIMAL(20, 2), realized_pl_pct DECIMAL(10, 4),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE investment.historical_prices (
            id SERIAL PRIMARY KEY, investment_id INTEGER REFERENCES investment.investments(id),
            snapshot_date DATE, price_usd DECIMAL(20, 8), price_idr DECIMAL(20, 2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(investment_id, snapshot_date)
        );

        CREATE TABLE investment.user_stats (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS market.ohlcv_cache (
            ticker TEXT, period TEXT, fetched_at TIMESTAMP, data BYTEA, 
            PRIMARY KEY (ticker, period)
        );
        
        CREATE TABLE IF NOT EXISTS market.latest_prices (
            ticker TEXT PRIMARY KEY, price DECIMAL(20, 8), timestamp TIMESTAMP,
            change_pct DECIMAL(10, 4), volume BIGINT, metadata TEXT
        );

        CREATE TABLE core.merchant_map (
            id SERIAL PRIMARY KEY, merchant_name TEXT UNIQUE, category TEXT, last_seen DATE
        );
        
        CREATE TABLE core.networth_snapshots (
            date DATE PRIMARY KEY, total_networth DECIMAL(15,2), 
            cash DECIMAL(15,2), bank_savings DECIMAL(15,2), 
            crypto DECIMAL(15,2), stocks DECIMAL(15,2), gold DECIMAL(15,2)
        );

        CREATE TABLE core.manual_balances (
            key TEXT PRIMARY KEY,
            value DECIMAL(15, 2) NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE core.cash_split (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            physical_cash DECIMAL(15, 2) NOT NULL DEFAULT 0,
            bank_savings DECIMAL(15, 2) NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE core.transfer_log (
            id SERIAL PRIMARY KEY,
            direction TEXT NOT NULL,
            amount DECIMAL(15, 2) NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE core.reward_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE core.behavioral_snapshots (
            id SERIAL PRIMARY KEY,
            snapshot_date DATE,
            data_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE core.settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE core.preferences (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE audit.audit_log (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            action TEXT,
            module TEXT,
            details TEXT,
            user_id TEXT
        );

        CREATE TABLE audit.predictions_audit (
            id SERIAL PRIMARY KEY,
            ticker TEXT,
            prediction_date DATE,
            predicted_value DECIMAL(20,8),
            actual_value DECIMAL(20,8),
            error_margin DECIMAL(10,4),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE audit.export_log (
            id SERIAL PRIMARY KEY,
            export_type TEXT,
            file_path TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit(); cur.close(); conn.close()

def migrate_batch(domain, sl_table, pg_table, sql_insert, row_mapper, filter_fn=None):
    print(f"Migrating {domain} ({pg_table})...")
    if not _valid_identifier(sl_table):
        return False, 0, [f"[{domain}] Invalid source table name refused: {sl_table!r}"]
    pg_conn = get_pg_conn()
    pg_cur = pg_conn.cursor()
    total = 0
    all_errors = []

    for db_path in SOURCES.get(domain, []):
        if not db_path.exists(): continue
        try:
            sl_conn = sqlite3.connect(str(db_path))
            sl_conn.row_factory = sqlite3.Row
            if not table_exists(sl_conn, sl_table):
                sl_conn.close()
                continue

            rows = sl_conn.execute(f"SELECT * FROM {sl_table}").fetchall()
            data = []
            for r in rows:
                row_dict = dict(r)
                if filter_fn and not filter_fn(row_dict, sl_conn):
                    continue
                try:
                    data.append(row_mapper(row_dict))
                except Exception as e:
                    all_errors.append(f"[{domain}] Mapping error for row {dict(r).get('id', 'unknown')}: {e}")

            if data:
                try:
                    extras.execute_batch(pg_cur, sql_insert, data)
                    total += len(data)
                except Exception as e:
                    pg_conn.rollback()
                    all_errors.append(f"[{domain}] Database error in {db_path.name}: {e}")
            sl_conn.close()
        except Exception as e:
            all_errors.append(f"[{domain}] Source error for {db_path.name}: {e}")

    if not all_errors:
        pg_conn.commit()
        print(f"  Done. Total rows: {total}")
        pg_cur.close(); pg_conn.close()
        return True, total, []
    else:
        pg_conn.rollback()
        print(f"  FAILED: {all_errors[0]}")
        pg_cur.close(); pg_conn.close()
        return False, total, all_errors

def filter_inv_child(r, sl_conn):
    cur = sl_conn.cursor()
    cur.execute("SELECT 1 FROM investments WHERE id = ?", (r["investment_id"],))
    return cur.fetchone() is not None

# Mappers
def map_exp(r):
    # Boolean conversion: SQLite 0/1 to Python True/False
    is_rec = True if r.get("is_recurring") in [1, "1", True, "True"] else False
    return (r["amount"], r["description"], r["category"], r.get("payment_method"), r["date"],
            is_rec, r.get("recurring_period"))

def map_inc(r):
    # Valid IncomeType enum values: SALARY, FREELANCE, INVESTMENT, SIDE_HUSTLE, OTHER
    raw_type = str(r.get("income_type", "other")).lower().strip()
    # Normalize some common variations
    mapping = {
        "transfer": "other", "gift": "other", "bonus": "salary",
        "dividends": "investment", "profit": "investment"
    }
    it = mapping.get(raw_type, raw_type)
    valid_types = ["salary", "freelance", "investment", "side-hustle", "other"]
    if it not in valid_types: it = "other"

    is_tx = True if r.get("is_taxed") in [1, "1", True, "True"] else False
    is_rec = True if r.get("is_recurring") in [1, "1", True, "True"] else False

    return (r["amount"], r["source"], it, r["date"], r.get("description"), is_tx, is_rec)

def map_inv(r):
    is_fav = True if r.get("is_favorite") in [1, "1", True, "True"] else False
    return (r["id"], r["asset_type"], r["ticker"], r["quantity"], r["buy_price"],
            r.get("buy_currency", "IDR"), r["buy_date"], r["status"], r["remaining_quantity"], is_fav)

def map_sell(r): return (r["investment_id"], r.get("ticker"), r["sell_date"], r["quantity"], r["sell_price"], r.get("sell_currency", "USD"), r.get("fees", 0), r["realized_pl_idr"], r["realized_pl_pct"])
def map_history(r): return (r["investment_id"], r["snapshot_date"], r["price_usd"], r["price_idr"])
def map_goal(r): return (r["name"], r["target_amount"], r["current_amount"], r.get("target_date"))
def map_budget(r): return (r["category"], r["limit_amt"], r["year"], r["month"])
def map_ohlcv(r):
    fa = r["fetched_at"]
    ts = datetime.fromtimestamp(fa) if isinstance(fa, (int, float)) else datetime.fromisoformat(fa.replace("Z", "+00:00"))
    ticker = f"{r['ticker']}_{r['period']}_1d"
    return (ticker, r["period"], ts, r["data"])
def map_merch(r): return (r["merchant_name"], r["category"], r.get("last_seen"))
def map_networth(r): return (r["date"], r["total_networth"], r["cash"], r["bank_savings"], r["crypto"], r["stocks"], r["gold"])
def map_cash(r): return (r["id"], r["physical_cash"], r["bank_savings"], r["updated_at"])
def map_bal(r): return (r["key"], r["value"], r["updated_at"])
def map_trans(r): return (r["direction"], r["amount"], r.get("note"), r["created_at"])
def map_reward(r): return (1, r["state_json"], r["updated_at"])
def map_behavioral(r): return (r.get("snapshot_date"), r["data_json"], r.get("created_at", datetime.now().isoformat()))
def map_audit(r):
    # SQLite audit_log: ts, ip, method, path, status_code, latency_ms, detail
    import json
    details = {
        "ip": r.get("ip"),
        "method": r.get("method"),
        "path": r.get("path"),
        "status_code": r.get("status_code"),
        "latency_ms": r.get("latency_ms"),
        "detail": r.get("detail")
    }
    return (r["ts"], "API_LOG", "GUI_BACKEND", json.dumps(details), None)
def map_recurrence(r): return (r["amount"], r["description"], r["category"], r["interval_days"], r["confidence"], r["last_seen"], r.get("status", "pending"))
def map_user_stats(r): return (r["key"], r["value"], r.get("updated_at", datetime.now().isoformat()))
def map_predictions_audit(r): return (r["ticker"], r["prediction_date"], r["predicted_value"], r["actual_value"], r["error_margin"], r.get("created_at", datetime.now().isoformat()))

def reset_sequences():
    conn = get_pg_conn(); cur = conn.cursor()
    tables = [
        ("financials", "expenses"), ("financials", "incomes"), ("financials", "budgets"),
        ("core", "goals"), ("investment", "investments"), ("investment", "sell_transactions"),
        ("investment", "historical_prices"), ("core", "merchant_map"), ("core", "transfer_log"),
        ("core", "behavioral_snapshots"), ("audit", "audit_log"), ("financials", "recurrence_candidates"),
        ("audit", "predictions_audit")
    ]
    for s, t in tables:
        if not (_valid_identifier(s) and _valid_identifier(t)):
            continue
        try:
            cur.execute(f"SELECT setval(pg_get_serial_sequence('{s}.{t}', 'id'), COALESCE(MAX(id), 1), false) FROM {s}.{t}")
        except: pass
    conn.commit(); cur.close(); conn.close()

def main():
    init_db()

    results = []

    # 1. High Priority Foundations
    results.append(migrate_batch("expense", "expenses", "financials.expenses",
        "INSERT INTO financials.expenses (amount, description, category, payment_method, date, is_recurring, recurring_period) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", map_exp))

    results.append(migrate_batch("income", "incomes", "financials.incomes",
        "INSERT INTO financials.incomes (amount, source, income_type, date, description, is_taxed, is_recurring) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", map_inc))

    results.append(migrate_batch("portfolio", "investments", "investment.investments",
        "INSERT INTO investment.investments (id, asset_type, ticker, quantity, buy_price, buy_currency, buy_date, status, remaining_quantity, is_favorite) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING", map_inv))

    # 2. Dependent Tables
    results.append(migrate_batch("portfolio", "sell_transactions", "investment.sell_transactions",
        "INSERT INTO investment.sell_transactions (investment_id, ticker, sell_date, quantity, sell_price_usd, sell_currency, fees, realized_pl_idr, realized_pl_pct) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", map_sell, filter_fn=filter_inv_child))

    results.append(migrate_batch("portfolio", "historical_prices", "investment.historical_prices",
        "INSERT INTO investment.historical_prices (investment_id, snapshot_date, price_usd, price_idr) VALUES (%s, %s, %s, %s) ON CONFLICT (investment_id, snapshot_date) DO UPDATE SET price_usd=EXCLUDED.price_usd, price_idr=EXCLUDED.price_idr", map_history, filter_fn=filter_inv_child))

    results.append(migrate_batch("portfolio", "user_stats", "investment.user_stats", "INSERT INTO investment.user_stats (key, value, updated_at) VALUES (%s, %s, %s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at", map_user_stats))

    # 3. Other Modules
    results.append(migrate_batch("goals", "goals", "core.goals", "INSERT INTO core.goals (name, target_amount, current_amount, target_date) VALUES (%s, %s, %s, %s) ON CONFLICT (name) DO UPDATE SET current_amount=EXCLUDED.current_amount", map_goal))
    results.append(migrate_batch("budget", "budgets", "financials.budgets", "INSERT INTO financials.budgets (category, limit_amt, year, month) VALUES (%s, %s, %s, %s) ON CONFLICT (category, year, month) DO UPDATE SET limit_amt=EXCLUDED.limit_amt", map_budget))
    results.append(migrate_batch("market", "ohlcv_cache", "market.ohlcv_cache", "INSERT INTO market.ohlcv_cache (ticker, period, fetched_at, data) VALUES (%s, %s, %s, %s) ON CONFLICT (ticker, period) DO UPDATE SET fetched_at=EXCLUDED.fetched_at, data=EXCLUDED.data", map_ohlcv))
    results.append(migrate_batch("merchant", "merchant_map", "core.merchant_map", "INSERT INTO core.merchant_map (merchant_name, category, last_seen) VALUES (%s, %s, %s) ON CONFLICT (merchant_name) DO UPDATE SET last_seen=EXCLUDED.last_seen", map_merch))
    results.append(migrate_batch("networth", "networth_snapshots", "core.networth_snapshots", "INSERT INTO core.networth_snapshots (date, total_networth, cash, bank_savings, crypto, stocks, gold) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (date) DO UPDATE SET total_networth=EXCLUDED.total_networth", map_networth))

    # 4. Core Accounting (Balances & Transfers)
    results.append(migrate_batch("goals", "cash_split", "core.cash_split", "INSERT INTO core.cash_split (id, physical_cash, bank_savings, updated_at) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET physical_cash=EXCLUDED.physical_cash, bank_savings=EXCLUDED.bank_savings, updated_at=EXCLUDED.updated_at", map_cash))
    results.append(migrate_batch("goals", "manual_balances", "core.manual_balances", "INSERT INTO core.manual_balances (key, value, updated_at) VALUES (%s, %s, %s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at", map_bal))
    results.append(migrate_batch("goals", "transfer_log", "core.transfer_log", "INSERT INTO core.transfer_log (direction, amount, note, created_at) VALUES (%s, %s, %s, %s)", map_trans))
    results.append(migrate_batch("goals", "reward_state", "core.reward_state", "INSERT INTO core.reward_state (id, state_json, updated_at) VALUES (%s, %s, %s) ON CONFLICT (id) DO UPDATE SET state_json=EXCLUDED.state_json, updated_at=EXCLUDED.updated_at", map_reward))
    results.append(migrate_batch("goals", "behavioral_snapshots", "core.behavioral_snapshots", "INSERT INTO core.behavioral_snapshots (snapshot_date, data_json, created_at) VALUES (%s, %s, %s)", map_behavioral))
    results.append(migrate_batch("goals", "settings", "core.settings", "INSERT INTO core.settings (key, value, updated_at) VALUES (%s, %s, %s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at", map_user_stats))
    results.append(migrate_batch("preferences", "preferences", "core.preferences", "INSERT INTO core.preferences (key, value, updated_at) VALUES (%s, %s, %s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at", map_user_stats))

    # 5. Audit & Recurrence
    results.append(migrate_batch("audit_log", "audit_log", "audit.audit_log", "INSERT INTO audit.audit_log (timestamp, action, module, details, user_id) VALUES (%s, %s, %s, %s, %s)", map_audit))
    results.append(migrate_batch("expense", "recurrence_candidates", "financials.recurrence_candidates", "INSERT INTO financials.recurrence_candidates (amount, description, category, interval_days, confidence, last_seen, status) VALUES (%s, %s, %s, %s, %s, %s, %s)", map_recurrence))
    results.append(migrate_batch("market", "predictions_audit", "audit.predictions_audit", "INSERT INTO audit.predictions_audit (ticker, prediction_date, predicted_value, actual_value, error_margin, created_at) VALUES (%s, %s, %s, %s, %s, %s)", map_predictions_audit))

    all_ok = all(r[0] for r in results)

    print("\n" + "="*50)
    print("MIGRATION SUMMARY")
    print("="*50)
    for i, (ok, count, errs) in enumerate(results):
        status = "✅" if ok else "❌"
        print(f"{status} Task {i+1}: {count} rows")
        for e in errs:
            print(f"    - ERROR: {e}")

    if all_ok:
        reset_sequences()
        print("\n🏆 ETL Migration Completed Successfully!")
    else:
        print("\n⚠️  Migration completed with ERRORS. Check the summary above.")
        exit(1)

if __name__ == "__main__":
    main()
