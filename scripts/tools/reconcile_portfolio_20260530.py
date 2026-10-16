import logging
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Root project path
ROOT = Path("C:/Users/Zhvn/Documents/Zhvny/Project/finance-tracker")
sys.path.insert(0, str(ROOT))

from packages.core.application.investment_service import InvestmentService
from packages.core.domain.models.investment import SellTransaction
from packages.core.infrastructure.config import Config
from packages.core.infrastructure.external.fx_service import FXService
from packages.core.infrastructure.investment_tracker.repository import PostgresRepository
from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager


def reconcile():
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    Config.initialize()
    # Force profile to personal
    Config._cached_profile = "personal"
    print(f"Active Profile: {Config.get_active_profile()}")

    # 1. Setup Repository and Service
    repo = PostgresRepository()

    # Monkey-patch missing methods to match IInvestmentRepository interface expected by InvestmentService
    # These methods use 'personal' schema implicitly via search_path (set by DatabaseManager based on Config.get_active_profile())

    if not hasattr(repo, 'add_sell_transaction'):
        def add_sell_transaction(sell: SellTransaction) -> int:
            sql = """
                INSERT INTO sell_transactions
                   (investment_id, sell_date, quantity, sell_price, sell_currency,
                    fees, realized_pl, ticker, sell_price_usd, realized_pl_idr, realized_pl_pct)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """

            sell_price_usd = sell.sell_price
            if sell.sell_currency.upper() == "IDR":
                sell_price_usd = sell.sell_price / sell.fx_rate if sell.fx_rate else sell.sell_price / Decimal("16000")

            return DatabaseManager.execute(sql, (
                sell.investment_id,
                sell.sell_date.date(),
                sell.quantity,
                sell.sell_price,
                sell.sell_currency,
                sell.fees,
                sell.realized_pl_idr,
                sell.ticker,
                sell_price_usd,
                sell.realized_pl_idr,
                sell.realized_pl_pct
            ))
        repo.add_sell_transaction = add_sell_transaction

    if not hasattr(repo, 'update_status'):
        def update_status(investment_id: int, status: str, remaining_qty: Decimal) -> bool:
            sql = "UPDATE investments SET status = %s, remaining_quantity = %s WHERE id = %s"
            return DatabaseManager.execute(sql, (status, remaining_qty, investment_id)) > 0
        repo.update_status = update_status

    if not hasattr(repo, 'get_all_lots_by_ticker'):
        def get_all_lots_by_ticker(ticker: str):
            return repo.get_active_lots(ticker)
        repo.get_all_lots_by_ticker = get_all_lots_by_ticker

    if not hasattr(repo, 'get_all_sell_transactions_by_ticker'):
        def get_all_sell_transactions_by_ticker(ticker: str):
            return []
        repo.get_all_sell_transactions_by_ticker = get_all_sell_transactions_by_ticker

    if not hasattr(repo, 'save_price_snapshot'):
        def save_price_snapshot(investment_id: int, date: datetime, price_usd: float, price_idr: float) -> bool:
            sql = """
                INSERT INTO historical_prices 
                   (investment_id, snapshot_date, price_usd, price_idr)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (investment_id, snapshot_date) DO UPDATE SET 
                    price_usd = EXCLUDED.price_usd, 
                    price_idr = EXCLUDED.price_idr
            """
            return DatabaseManager.execute(sql, (investment_id, date.date(), price_usd, price_idr)) is not None
        repo.save_price_snapshot = save_price_snapshot

    fx_service = FXService()
    service = InvestmentService(repository=repo, fx_service=fx_service)

    # 2. Execute Transactions
    print("\n--- Starting Portfolio Reconciliation (2026-05-30) ---")

    # AAPL (Lot 8): Sell 0.12408647 shares at $191.29 (2026-05-30)
    print("Selling AAPL Lot 8...")
    try:
        res_aapl = service.sell_investment(
            investment_id=8,
            quantity=Decimal("0.12408647"),
            sell_price=Decimal("191.29"),
            sell_currency="USD",
            sell_date=datetime(2026, 5, 30)
        )
        print(f"  AAPL SUCCESS: PL IDR={res_aapl['pl_idr']}, New Status={res_aapl['new_status']}")
    except Exception as e:
        print(f"  AAPL FAILED: {e}")

    # AMZN (Lots 7, 9, 16): Sell 1.27926373 shares at $181.28 (2026-05-30)
    print("Selling AMZN Lots 7, 9, 16...")
    for amzn_id in [7, 9, 16]:
        try:
            inv = repo.get_by_id(amzn_id)
            if inv and inv.remaining_quantity > 0:
                res_amzn = service.sell_investment(
                    investment_id=amzn_id,
                    quantity=inv.remaining_quantity,
                    sell_price=Decimal("181.28"),
                    sell_currency="USD",
                    sell_date=datetime(2026, 5, 30)
                )
                print(f"  AMZN Lot {amzn_id} SUCCESS: PL IDR={res_amzn['pl_idr']}, New Status={res_amzn['new_status']}")
            else:
                print(f"  AMZN Lot {amzn_id} skipped: Not found or already sold.")
        except Exception as e:
            print(f"  AMZN Lot {amzn_id} FAILED: {e}")

    # NVDA (Lots 4, 6): Sell 0.80683736 shares at $1,064.69 (2026-05-28)
    print("Selling NVDA Lots 4, 6...")
    for nvda_id in [4, 6]:
        try:
            inv = repo.get_by_id(nvda_id)
            if inv and inv.remaining_quantity > 0:
                res_nvda = service.sell_investment(
                    investment_id=nvda_id,
                    quantity=inv.remaining_quantity,
                    sell_price=Decimal("1064.69"),
                    sell_currency="USD",
                    sell_date=datetime(2026, 5, 28)
                )
                print(f"  NVDA Lot {nvda_id} SUCCESS: PL IDR={res_nvda['pl_idr']}, New Status={res_nvda['new_status']}")
            else:
                print(f"  NVDA Lot {nvda_id} skipped: Not found or already sold.")
        except Exception as e:
            print(f"  NVDA Lot {nvda_id} FAILED: {e}")

    # GOOG: Buy 0.3941432 shares at $177.60 (2026-05-28)
    print("Buying GOOG...")
    try:
        # Check if already bought in previous partial run
        existing = DatabaseManager.query("SELECT id FROM investments WHERE ticker = 'GOOG' AND buy_date = '2026-05-28' AND quantity = 0.3941432")
        if existing:
            print(f"  GOOG already exists with ID: {existing[0]['id']}")
        else:
            new_goog_id = service.add_investment(
                asset_type="stock",
                ticker="GOOG",
                quantity=Decimal("0.3941432"),
                buy_price=Decimal("177.60"),
                buy_currency="USD",
                buy_date=datetime(2026, 5, 28)
            )
            print(f"  GOOG added with ID: {new_goog_id}")
    except Exception as e:
        print(f"  GOOG Buy FAILED: {e}")


    # GOLD (Lot 18): Sell 0.8g at ~$146.70/g (2026-05-30)
    print("Selling 0.8g GOLD from Lot 18...")
    try:
        res_gold = service.sell_investment(
            investment_id=18,
            quantity=Decimal("0.8"),
            sell_price=Decimal("146.70"),
            sell_currency="USD",
            sell_date=datetime(2026, 5, 30)
        )
        print(f"  GOLD SUCCESS: PL IDR={res_gold['pl_idr']}, Remaining Qty={res_gold['new_remaining']}, New Status={res_gold['new_status']}")
    except Exception as e:
        print(f"  GOLD FAILED: {e}")

    print("\n--- Reconciliation Complete ---")

if __name__ == "__main__":
    reconcile()
