
import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from packages.core.application.investment_service import InvestmentService
from packages.core.infrastructure.external.fx_service import FXService
from packages.core.infrastructure.persistence.postgres_investment_repository import PostgresInvestmentRepository
from packages.database.index import connect, db, disconnect


async def verify():
    await connect()
    try:
        repo = PostgresInvestmentRepository()
        fx_service = FXService()
        service = InvestmentService(repo, fx_service)

        print("--- Refreshing Prices ---")
        refresh_result = service.refresh_prices()
        print(f"Refresh Result: {refresh_result}")

        print("\n--- Fetching Active Investments ---")
        investments = service.get_active_investments()
        print(f"Total Investments: {len(investments)}")

        for inv in investments:
            print(f"Ticker: {inv['ticker']}")
            print(f"  Price IDR: {inv['current_price_idr']}")
            print(f"  Cap Gain: {inv['cap_gain']}")
            print(f"  FX Gain: {inv['fx_gain']}")
            print(f"  Is Stale: {inv['is_stale']}")
            print("-" * 20)

        # Check DB directly
        count = await db.historicalprice.count()
        print(f"\nTotal Historical Price Snapshots: {count}")

    finally:
        await disconnect()

if __name__ == "__main__":
    asyncio.run(verify())
