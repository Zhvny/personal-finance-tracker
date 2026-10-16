
import sys
from pathlib import Path

# Add project root to sys.path
_HERE = Path(__file__).resolve()
root = _HERE.parent.parent.parent.parent # ../../../..
sys.path.insert(0, str(root))

from packages.core.application.investment_service import InvestmentService
from packages.core.infrastructure.persistence.postgres_investment_repository import PostgresInvestmentRepository
from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager


def test():
    DatabaseManager.initialize()
    repo = PostgresInvestmentRepository()
    service = InvestmentService(repo)

    results = service.get_active_investments()
    print("--- Results from Service ---")
    import json
    print(json.dumps(results, indent=2, default=str))

if __name__ == "__main__":
    test()
