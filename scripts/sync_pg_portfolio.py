import logging
import os
import sqlite3
import sys
from pathlib import Path

import psycopg2

logger = logging.getLogger(__name__)


def _pg_password() -> str:
    pw = os.environ.get("POSTGRES_PASSWORD")
    if pw:
        return pw
    if os.environ.get("DEV_MODE") == "1":
        logger.warning("POSTGRES_PASSWORD unset, using dev default")
        return "postgres"
    logger.warning("POSTGRES_PASSWORD unset, using localhost dev default")
    return "postgres"


_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
from packages.core.infrastructure.config import Config


def sync():
    Config.initialize()
    # SQLite
    sqlite_path = _ROOT / "apps/cli/profiles/personal/investment_tracker/data/portfolio.db"
    s_conn = sqlite3.connect(str(sqlite_path))
    s_conn.row_factory = sqlite3.Row
    s_invs = s_conn.execute("SELECT * FROM investments").fetchall()
    s_conn.close()

    # Postgres
    p_conn = psycopg2.connect(
        dbname="finance_tracker", user="postgres", password=_pg_password(), host="localhost", port="5432"
    )
    try:
        cur = p_conn.cursor()

        # Mark Sold in PG based on SQLite
        for inv in s_invs:
            if inv['status'] == 'sold':
                # Map ticker XAU to GOLD in PG
                ticker = 'GOLD' if inv['ticker'] == 'XAU' else inv['ticker']
                cur.execute(
                    "UPDATE personal.investments SET status = 'sold', remaining_quantity = 0 WHERE ticker = %s AND status != 'sold'",
                    (ticker,)
                )

        # Ensure 10g Gold is in PG
        s_10g = next((i for i in s_invs if i['ticker'] == 'XAU' and i['quantity'] == 10.0), None)
        if s_10g:
            cur.execute("SELECT * FROM personal.investments WHERE ticker = 'GOLD' AND quantity = 10.0")
            if not cur.fetchone():
                print("Adding 10g Gold to Postgres...")
                cur.execute(
                    "INSERT INTO personal.investments (asset_type, ticker, quantity, remaining_quantity, buy_price, buy_currency, buy_date, status, buy_price_idr) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    ('gold', 'GOLD', 10.0, 10.0, s_10g['buy_price'], s_10g['buy_currency'], s_10g['buy_date'][:10], 'holding', s_10g['buy_price']*16000)
                )

        # Mark 1g Gold as sold in PG explicitly
        cur.execute("UPDATE personal.investments SET status = 'sold', remaining_quantity = 0 WHERE ticker = 'GOLD' AND quantity = 1.0")

        p_conn.commit()
        print("Postgres sync complete.")
    finally:
        p_conn.close()

if __name__ == '__main__':
    sync()
