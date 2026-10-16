
import logging
import os

import psycopg2

logger = logging.getLogger(__name__)


def check():
    pw = os.environ.get("POSTGRES_PASSWORD")
    if not pw:
        if os.environ.get("DEV_MODE") == "1":
            logger.warning("POSTGRES_PASSWORD unset, using dev default")
        else:
            logger.warning("POSTGRES_PASSWORD unset, using localhost dev default")
        pw = "postgres"
    conn = psycopg2.connect(dbname="finance_tracker", user="postgres", password=pw, host="localhost")
    cur = conn.cursor()
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='personal' AND table_name='expenses'")
    print(cur.fetchall())
    conn.close()

if __name__ == "__main__":
    check()
