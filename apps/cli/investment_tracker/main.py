#!/usr/bin/env python3
import sys
from pathlib import Path

# Add monorepo root to sys.path to access shared packages
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from packages.core.application.investment_service import BlockingError, IntegrityError, InvestmentService
from packages.core.domain.models import Investment
from packages.core.infrastructure.investment_tracker.sqlite_repository import (
    SQLiteInvestmentRepository as InvestmentRepository,
)

# Initialize DatabaseManager for Postgres redirection
try:
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
    DatabaseManager.initialize()
except Exception:
    pass

# Local imports
try:
    from apps.cli.investment_tracker.core.calculator import ProfitCalculator
    from apps.cli.investment_tracker.services import get_price_service_factory
    from apps.cli.investment_tracker.services.discipline_service import DisciplineService
    from apps.cli.investment_tracker.services.historical_service import HistoricalDataService
    from apps.cli.investment_tracker.services.risk_service import RiskService
    from apps.cli.investment_tracker.services.sell_service import SellService
    from apps.cli.investment_tracker.ui.cli_view import CLIView
    from apps.cli.prediction_service import PredictionService
except ImportError:
    # Fallback for different run modes
    from apps.cli.investment_tracker.core.calculator import ProfitCalculator
    from apps.cli.investment_tracker.services import get_price_service_factory
    from apps.cli.investment_tracker.services.discipline_service import DisciplineService
    from apps.cli.investment_tracker.services.historical_service import HistoricalDataService
    from apps.cli.investment_tracker.services.risk_service import RiskService
    from apps.cli.investment_tracker.services.sell_service import SellService
    from apps.cli.investment_tracker.ui.cli_view import CLIView
    from apps.cli.prediction_service import PredictionService

import msvcrt
import time
from datetime import datetime
from decimal import Decimal

from rich.live import Live

from packages.core.infrastructure.config import Config


class PortfolioApp:
    def __init__(self):
        # Initialize with profile-aware database path
        db_path = Config.get_db_path("investment")
        self.repo         = InvestmentRepository(db_path=db_path)
        self.view         = CLIView()
        self.price_factory = get_price_service_factory()
        self.calculator   = ProfitCalculator()
        self.hist_service = HistoricalDataService()
        self.sell_service = SellService(self.price_factory.fx_service)
        self.investment_service = InvestmentService(self.repo)
        self.discipline   = DisciplineService(self.repo)
        self.running      = True

    def run(self):
        actions = {
            "1": self.quick_add,
            "2": self.quick_check,
            "3": self.view_portfolio,
            "4": self.pl_analysis,
            "5": self.ml_sniper_advice,
            "10": self.agent_senate_advice,
            "11": self.butterfly_analysis,
            "12": self.whale_profiler,
            "6": self.edit_delete,
            "7": self.sell_asset,
            "8": self.view_realized_pl,
            "9": self.clean_db,
        }
        while self.running:
            choice = self.view.show_main_menu(self.discipline.get_status())
            if choice == "0":
                self.running = False
            elif choice in actions:
                actions[choice]()
            else:
                self.view.show_error("Invalid choice")

    def whale_profiler(self):
        ticker = input("Enter Ticker: ").upper()
        cat = input("Enter Category (us/idx/crypto): ").lower()
        asset_type = "stock"
        if cat == "crypto": asset_type = "crypto"
        elif cat == "idx": asset_type = "idx"
        self.view.show_info(f"Analyzing volume patterns for {ticker}...")
        try:
            from packages.core.application.investment_tracker.whale_service import WhaleVolumeProfiler
        except ImportError:
            # Fallback for dev environments where packages/core might not be in sys.path correctly
            # though run-cli.bat should handle this.
            from packages.core.application.investment_tracker.whale_service import WhaleVolumeProfiler
        profiler = WhaleVolumeProfiler()
        result = profiler.analyze_ticker(ticker, asset_type)
        self.view.show_whale_analysis(result)
        input("\nPress Enter...")

    def quick_add(self):
        inv = self.view.get_investment_input()
        if not inv: return
        res = PredictionService.get_prediction(inv.ticker, inv.asset_type)
        if res.get('status') == 'success':
            pred = res['data']
            print("\n" + "="*40)
            print(" [ML SNIPER ADVICE]")
            print(RiskService.get_surgical_advice(inv.ticker, inv.buy_price, pred))
            print("="*40 + "\n")
        if input("\nPreview P/L chart before saving? (y/n): ").lower() == "y":
            try: self._show_pl_chart(inv)
            except Exception as e: print(f"Chart preview failed: {e}")
        if input("Save to database? (y/n): ").lower() == "y":
            inv_id = self.repo.save(inv)
            active_invs = self.repo.get_all_active()
            prices = self._fetch_prices(active_invs)
            total_v = 0
            for a_inv in active_invs:
                p = prices.get(a_inv.id)
                if p: total_v += a_inv.remaining_quantity * p['current_price_idr']
            events = self.discipline.evaluate_investment(inv, total_v)
            self.view.show_discipline_events(events)
            try:
                self._generate_history(inv_id, inv)
                self.view.show_success(f"Saved! ID: {inv_id}")
            except Exception as e:
                self.view.show_success(f"Saved! ID: {inv_id} (no history: {e})")

    def quick_check(self):
        self.view.show_info("QUICK CHECK MODE (not saved)")
        inv = self.view.get_investment_input(mode="CHECK")
        if inv:
            res = PredictionService.get_prediction(inv.ticker, inv.asset_type)
            if res.get('status') == 'success':
                pred = res['data']
                print("\n" + "="*40)
                print(" [ML SNIPER ADVICE]")
                print(RiskService.get_surgical_advice(inv.ticker, inv.buy_price, pred))
                print("="*40 + "\n")
            try: self._show_pl_chart(inv)
            except Exception as e: self.view.show_error(f"Error: {e}")

    def ml_sniper_advice(self):
        ticker = input("Enter Ticker: ").upper()
        cat = input("Enter Category (us/idx/crypto/forex/commodities): ").lower()
        res = PredictionService.get_prediction(ticker, cat)
        if res.get('status') == 'success':
            pred = res['data']
            print("\n" + "="*40)
            print(f" [ML SNIPER ANALYSIS: {ticker}]")
            print(RiskService.get_surgical_advice(ticker, pred['last_close'], pred))
            print("="*40)
        else: print(f"\nNo ML model found for {ticker} in {cat}.")
        input("\nPress Enter...")

    def agent_senate_advice(self):
        ticker = input("Enter Ticker: ").upper()
        cat = input("Enter Category (us/idx/crypto/forex/commodities): ").lower()
        self.view.show_info(f"Assembling Agent Senate for {ticker}...")
        df = self._load_ticker_df(ticker, cat)
        if df is None:
            self.view.show_error(f"Could not load data for {ticker}. Check category.")
            return
        try: from services.senate_service import SenateService
        except ImportError: from apps.cli.investment_tracker.services.senate_service import SenateService
        senate = SenateService(cat)
        result = senate.get_senate_decision(ticker, df)
        self.view.show_senate_advice(ticker, result)
        input("\nPress Enter...")

    def butterfly_analysis(self):
        ticker = input("Enter Ticker: ").upper()
        cat = input("Enter Category (us/idx/crypto/forex/commodities): ").lower()
        self.view.show_info(f"Mapping cross-market risks for {ticker}...")
        try: from services.butterfly_service import ButterflyService
        except ImportError: from apps.cli.investment_tracker.services.butterfly_service import ButterflyService
        svc = ButterflyService()
        nodes = svc.get_risk_map(ticker, cat)
        if not nodes:
            self.view.show_error(f"No correlation data available for {ticker}.")
            return
        self.view.show_butterfly_map(ticker, nodes)
        input("\nPress Enter...")

    def _load_ticker_df(self, ticker: str, cat: str):
        import pandas as pd
        root = Path(__file__).resolve().parent.parent.parent.parent
        raw_base = root / "apps" / "cli" / "stock_ml" / "data" / "raw"
        raw_fpath = raw_base / cat / f"{ticker}.csv"
        if not raw_fpath.exists(): return None
        try:
            df = pd.read_csv(raw_fpath, index_col=0, parse_dates=True)
            df.columns = [c.capitalize() for c in df.columns]
            return df
        except Exception: return None

    def view_portfolio(self):
        invs = self.repo.get_all_active()
        if not invs:
            self.view.show_info("Portfolio empty (no active holdings)")
            return
        self.view.show_info("Fetching latest market prices...")
        prices = self._fetch_prices(invs)
        last_updated = datetime.now()
        with Live(self.view.get_portfolio_table(invs, prices, last_updated), refresh_per_second=4) as live:
            start_time = time.time()
            while True:
                if not sys.stdin.isatty():
                    break
                is_open = self._is_market_open()
                interval = 300 if is_open else 1800
                elapsed = time.time() - start_time
                if elapsed > interval:
                    prices = self._fetch_prices(invs)
                    last_updated = datetime.now()
                    start_time = time.time()
                    live.update(self.view.get_portfolio_table(invs, prices, last_updated))
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                    if key in ['\r', '\n', 'q']: break
                    if key == 'f':
                        live.stop()
                        print("\n[FAVORITE TOGGLE MODE]")
                        try:
                            inv_id = int(input("Enter Investment ID to toggle star: "))
                            self.repo.toggle_favorite(inv_id)
                            invs = self.repo.get_all_active()
                            live.update(self.view.get_portfolio_table(invs, prices, last_updated))
                        except ValueError: print("Invalid ID")
                        live.start()
                time.sleep(0.1)

    def _is_market_open(self) -> bool:
        now = datetime.now()
        if now.weekday() >= 5: return False
        return 9 <= now.hour < 17

    def pl_analysis(self):
        invs = self.repo.get_all_active()
        if not invs:
            self.view.show_info("No investments")
            return
        inv_id = self.view.select_investment(invs, "analyze")
        if not inv_id: return
        inv     = self.repo.get_by_id(inv_id)
        history = self.repo.get_all_snapshots(inv_id)
        if not history:
            self.view.show_info("No historical data found.")
            input("\nPress Enter...")
            return

        is_idx = inv.ticker.upper().endswith(".JK")
        if is_idx:
            buy_price = float(inv.buy_price_idr) if inv.buy_price_idr else float(inv.buy_price)
            db_history = [{"date": datetime.fromisoformat(h["snapshot_date"]), "close": h["price_idr"]}
                          for h in history]
        else:
            buy_price = self._to_usd(inv.buy_price, inv.buy_currency)
            db_history = [{"date": datetime.fromisoformat(h["snapshot_date"]), "close": h["price_usd"]}
                          for h in history]

        chart = self.hist_service.generate_pl_journey(db_history, buy_price, inv.quantity, inv.buy_date, ticker=inv.ticker)
        print(chart)
        input("\nPress Enter...")

    def edit_delete(self):
        invs = self.repo.get_all_active()
        if not invs:
            self.view.show_info("No investments")
            return
        inv_id = self.view.select_investment(invs, "edit/delete")
        if not inv_id: return
        print("\n1. Edit\n2. Delete")
        if input("Choose: ").strip() == "2":
            if input("Confirm delete? (y/n): ").lower() == "y":
                try:
                    if self.investment_service.delete_investment(inv_id):
                        self.view.show_success("Deleted")
                    else:
                        self.view.show_error("Failed to delete (ID not found)")
                except (BlockingError, IntegrityError) as e:
                    self.view.show_error(str(e))
                except Exception as e:
                    self.view.show_error(f"Error: {e}")

    def sell_asset(self):
        tickers = self.repo.get_active_tickers()
        if not tickers:
            self.view.show_info("No active holdings to sell.")
            input("Press Enter...")
            return

        selected = self.view.select_ticker(tickers)
        if not selected:
            return

        ticker = selected["ticker"]
        asset_type = selected["asset_type"]
        total_holding = selected["total_qty"]

        sell_input = self.view.get_fifo_sell_input(ticker, total_holding)
        if not sell_input:
            return

        lots = self.repo.get_active_lots(ticker, asset_type)
        try:
            from packages.core.domain.models import SellTransaction
            result = self.sell_service.execute_fifo_sell(
                lots=lots,
                quantity=sell_input.quantity,
                sell_price=sell_input.sell_price,
                sell_currency=sell_input.sell_currency,
                sell_date=sell_input.sell_date,
                fees=sell_input.fees
            )

            # Save transactions for each lot
            for detail in result.lot_details:
                lot_inv = detail["investment"]
                # Construct a SellTransaction for this specific lot slice
                lot_sell = SellTransaction(
                    sell_date=sell_input.sell_date,
                    quantity=detail["qty"],
                    sell_price=sell_input.sell_price,
                    sell_currency=sell_input.sell_currency,
                    fees=detail["fees"]
                )
                lot_sell.realized_pl = detail["realized_pl"]
                # Calculate local P/L % for this lot slice
                # Use buy_price_idr from the lot
                buy_val = lot_inv.buy_price_idr * detail["qty"]
                lot_sell.realized_pl_pct = (detail["realized_pl"] / buy_val * 100) if buy_val else 0

                self.repo.save_sell_transaction(lot_inv.id, lot_inv, lot_sell)

            self.view.show_sell_confirmation(result)
            input("\nPress Enter...")
        except ValueError as e:
            self.view.show_error(str(e))

    def view_realized_pl(self):
        sells = self.repo.get_realized_pl()
        self.view.clear()
        if sells: self.view.show_sell_history(sells)
        else: self.view.show_info("No realized P/L records found.")
        input("\nPress Enter...")

    def clean_db(self):
        if input("\n  Confirm cleanup? (y/n): ").lower() != "y":
            self.view.show_info("Cancelled.")
            return
        try:
            result = self.investment_service.prune_sold_lots()
            self.view.show_success(f"Cleaned up {result['deleted']} sold lots.")
        except Exception as e:
            self.view.show_error(f"Cleanup failed: {e}")
        input("\nPress Enter...")

    def _to_usd(self, price: float, currency: str) -> float:
        return price / self.price_factory.fx_service.get_usd_idr() if currency.upper() == "IDR" else price

    def _show_pl_chart(self, inv: Investment):
        is_idx = inv.ticker.upper().endswith(".JK")
        if is_idx:
            buy_price = float(inv.buy_price_idr) if inv.buy_price_idr else float(inv.buy_price)
        else:
            buy_price = self._to_usd(inv.buy_price, inv.buy_currency)

        history = self.hist_service.get_weekly_history(inv.ticker, inv.asset_type, inv.buy_date)
        chart   = self.hist_service.generate_pl_journey(history, buy_price, inv.quantity, inv.buy_date, ticker=inv.ticker)
        print(chart)
        input("\nPress Enter...")

    def _generate_history(self, inv_id: int, inv: Investment):
        history = self.hist_service.get_weekly_history(
            inv.ticker, inv.asset_type, inv.buy_date,
            fx_service=self.price_factory.fx_service
        )
        usd_idr = self.price_factory.fx_service.get_usd_idr()
        for h in history:
            close = h["close"]
            is_idr = False
            if inv.asset_type == "gold" and close > 100_000: is_idr = True
            elif inv.ticker.upper().endswith(".JK"): is_idr = True
            if is_idr:
                p_idr = close
                p_usd = p_idr / usd_idr
            else:
                p_usd = close
                p_idr = p_usd * usd_idr
            self.repo.save_price_snapshot(inv_id, h["date"], p_usd, p_idr)

    def _fetch_prices(self, invs) -> dict:
        prices = {}
        for inv in invs:
            try:
                svc = self.price_factory.get_service(inv.asset_type)
                fetched = svc.get_prices(inv)
                # Ensure structure is consistent
                prices[inv.id] = {
                    "usd": Decimal(str(fetched.get("usd", 0))),
                    "idr": Decimal(str(fetched.get("idr", 0))),
                    "buy_price_idr": inv.buy_price_idr or Decimal("0"),
                    "current_price_idr": Decimal(str(fetched.get("current_price_idr", fetched.get("idr", 0)))),
                    "stale": False,
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            except Exception:
                stale = self.repo.get_latest_snapshot(inv.id)
                if stale:
                    prices[inv.id] = {
                        "usd": stale.get("price_usd", Decimal("0")),
                        "idr": stale.get("price_idr", Decimal("0")),
                        "buy_price_idr": inv.buy_price_idr or Decimal("0"),
                        "current_price_idr": stale.get("price_idr", Decimal("0")),
                        "stale": True,
                        "last_updated": stale.get("date") or stale.get("snapshot_date") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                else:
                    # Robust fallback if NO snapshot exists
                    # Use buy_price_idr as current_price_idr to show 0% P/L instead of "—"
                    fallback_price = inv.buy_price_idr or Decimal("0")
                    prices[inv.id] = {
                        "usd": Decimal("0.0"),
                        "idr": fallback_price,
                        "buy_price_idr": fallback_price,
                        "current_price_idr": fallback_price,
                        "stale": True,
                        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
        return prices

def main():
    app = PortfolioApp()
    try: app.run()
    except KeyboardInterrupt: print("\nBye!")

if __name__ == "__main__":
    main()
