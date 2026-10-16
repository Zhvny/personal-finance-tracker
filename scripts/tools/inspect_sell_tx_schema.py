import sys
from pathlib import Path

ROOT = Path("C:/Users/Zhvn/Documents/Zhvny/Project/finance-tracker")
sys.path.insert(0, str(ROOT))

from packages.core.infrastructure.config import Config
from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager


def check():
    Config.initialize()
    sql = "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'sell_transactions' AND table_schema = 'personal' ORDER BY ordinal_position"
    rows = DatabaseManager.query(sql, schema='personal')
    for row in rows:
        print(row)

if __name__ == "__main__":
    check()
