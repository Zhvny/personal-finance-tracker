import logging
import os
import sqlite3
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


def verify():
    # SQLite
    root = Path(__file__).resolve().parent.parent
    s_path = str(root / "apps/cli/profiles/personal/investment_tracker/data/portfolio.db")
    s_conn = sqlite3.connect(s_path)
    s_active = s_conn.execute("SELECT ticker, quantity, status FROM investments WHERE status != 'sold'").fetchall()
    print("SQLite Active Holdings:")
    for row in s_active:
        print(f"  {row[0]}: {row[1]} ({row[2]})")
    s_conn.close()

    # PG
    p_conn = psycopg2.connect(
        dbname="finance_tracker", user="postgres", password=_pg_password(), host="localhost", port="5432"
    )
    cur = p_conn.cursor()
    cur.execute("SELECT ticker, quantity, status FROM personal.investments WHERE status != 'sold'")
    p_active = cur.fetchall()
    print("\nPostgres Active Holdings:")
    for row in p_active:
        print(f"  {row[0]}: {row[1]} ({row[2]})")
    p_conn.close()

if __name__ == '__main__':
    verify()
