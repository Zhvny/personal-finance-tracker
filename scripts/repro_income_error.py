import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.infrastructure.config import Config
from packages.core.infrastructure.persistence.postgres_income_repository import PostgresIncomeRepository


def reproduce():
    Config.initialize()
    print(f"Active Profile: {Config.get_active_profile()}")

    repo = PostgresIncomeRepository()
    try:
        summary = repo.get_monthly_summary(2026, 5)
        print(f"Summary: {summary}")
    except Exception as e:
        print(f"Caught Error: {e}")

if __name__ == "__main__":
    reproduce()
