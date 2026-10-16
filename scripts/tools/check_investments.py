import sys
from pathlib import Path

ROOT = Path("C:/Users/Zhvn/Documents/Zhvny/Project/finance-tracker")
sys.path.insert(0, str(ROOT))

from packages.core.infrastructure.config import Config
from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager


def check():
    Config.initialize()
    ids = (8, 7, 9, 16, 4, 6, 18)
    sql = "SELECT id, ticker, quantity, remaining_quantity, status FROM investments WHERE id IN %s"
    rows = DatabaseManager.query(sql, (ids,), schema='personal')
    for row in rows:
        print(row)

if __name__ == "__main__":
    check()
