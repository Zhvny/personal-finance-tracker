import os
import sys
from datetime import datetime, timedelta

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from packages.core.application.investment_tracker.investment_service import InvestmentService
from packages.core.application.investment_tracker.sell_service import SellService
from packages.core.infrastructure.persistence.sqlite_investment_repository import SQLiteInvestmentRepository

from packages.core.domain.models.investment import InvestmentStatus


def verify_strict_lot_tracking():
    print("--- Verifying Strict Lot Tracking ---")

    # 1. Setup - use a temporary test DB
    test_db = "test_lot_tracking.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    repo = SQLiteInvestmentRepository(db_path=test_db)
    service = InvestmentService(repo)
    sell_service = SellService(repo)

    # 2. Add Investment
    print("\n[Step 1] Adding Investment (Lot 1)...")
    # We'll use USD to trigger FX conversion
    buy_date = datetime.now() - timedelta(days=10)
    inv_id = service.add_investment(
        asset_type="stock",
        ticker="AAPL",
        quantity=10,
        buy_price=150.0,
        buy_currency="USD",
        buy_date=buy_date
    )

    # Verify persistence
    lot = repo.get_by_id(inv_id)
    print(f"Lot 1 added with ID: {inv_id}")
    print(f"Stored Buy Price (USD): {lot.buy_price}")
    print(f"Stored Buy Price (IDR): {lot.buy_price_idr}")
    print(f"Stored FX Rate: {lot.buy_fx_rate}")

    if lot.buy_price_idr is None or lot.buy_fx_rate is None:
        print("FAILED: buy_price_idr or buy_fx_rate is None")
        return

    # 3. Modify stored IDR price to simulate a specific cost basis (Strict Tracking check)
    print("\n[Step 2] Manually adjusting stored IDR price to verify strict tracking usage...")
    # Normally we wouldn't do this, but for verification we want to see if SellService uses this specific value
    # instead of re-calculating it from buy_price * fx_buy
    target_buy_price_idr = 2_000_000.0 # Arbitrary high value
    from packages.core.infrastructure.persistence.database import Database
    Database.execute(test_db, "UPDATE investments SET buy_price_idr = ? WHERE id = ?", (target_buy_price_idr, inv_id))

    lot_updated = repo.get_by_id(inv_id)
    print(f"New Stored Buy Price (IDR): {lot_updated.buy_price_idr}")

    # 4. Sell part of the lot
    print("\n[Step 3] Selling 5 units...")
    sell_price_usd = 200.0
    sell_currency = "USD"

    result = sell_service.sell_investment(
        investment_id=inv_id,
        quantity=5,
        sell_price=sell_price_usd,
        sell_currency=sell_currency
    )

    fx_sell = result["fx_sell"]
    sell_price_idr = sell_price_usd * fx_sell

    # Expected P/L = (Sell Price IDR - target_buy_price_idr) * 5
    expected_pl = (sell_price_idr - target_buy_price_idr) * 5

    print(f"Sell Price (IDR): {sell_price_idr}")
    print(f"Calculated Realized P/L: {result['pl_idr']}")
    print(f"Expected Realized P/L: {expected_pl}")

    if abs(result["pl_idr"] - expected_pl) < 0.01:
        print("SUCCESS: SellService used the stored buy_price_idr!")
    else:
        print("FAILED: SellService did NOT use the stored buy_price_idr or used a different value.")

    # 5. Partial Sold check
    lot_after_sell = repo.get_by_id(inv_id)
    print("\n[Step 4] Checking lot status...")
    print(f"Remaining Quantity: {lot_after_sell.remaining_quantity}")
    print(f"Status: {lot_after_sell.status}")

    if lot_after_sell.status == InvestmentStatus.PARTIAL_SOLD:
        print("SUCCESS: Status updated to partial_sold.")
    else:
        print(f"FAILED: Status is {lot_after_sell.status}")

    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)

if __name__ == "__main__":
    verify_strict_lot_tracking()
