import logging
import os
import sys

# Menambahkan direktori root ke path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apps.cli.stock_analyzer.adapters.cleaner import DataCleaner
from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
from apps.cli.stock_analyzer.adapters.indicators import IndicatorEngine
from apps.cli.stock_analyzer.domain.config import AppConfig
from apps.cli.stock_analyzer.domain.scoring import ScoringEngine
from apps.cli.stock_analyzer.use_cases.backtester import Backtester


def main():
    if len(sys.argv) < 2:
        print("Usage: python backtest_ticker.py <TICKER> [period]")
        sys.exit(1)

    ticker = sys.argv[1]
    period = sys.argv[2] if len(sys.argv) > 2 else "2y"

    # Setup components
    logging.basicConfig(level=logging.ERROR)
    fetcher = DataFetcher()
    cleaner = DataCleaner()
    indicators = IndicatorEngine()
    scoring = ScoringEngine()
    config = AppConfig.load()

    backtester = Backtester(fetcher, cleaner, indicators, scoring, config)

    print(f"--- Backtesting {ticker} ({period}) ---")
    try:
        result = backtester.run(ticker, period)

        if result.total_trades == 0:
            print("Tidak ada trade yang terdeteksi.")
            return

        print(f"Total Trades    : {result.total_trades}")
        print(f"Win Rate        : {result.win_rate:.2f}%")
        print(f"Total Return    : {result.total_return_pct:.2f}%")
        print(f"Avg Return/Trade: {result.avg_return_pct:.2f}%")
        print(f"Max Drawdown    : {result.max_drawdown_pct:.2f}%")
        print(f"Portfolio Return: {result.portfolio_final_return:.2f}% (Simulasi Risk 2%/Trade)")
        print("Max Risk Allowed: 3.00% (Hard Stop)")

        print("\n--- Trade History ---")
        print(f"{'Entry Date':<12} | {'Exit Date':<12} | {'Entry':<8} | {'Exit':<8} | {'PnL%':<6} | {'Reason'}")
        print("-" * 75)
        for t in result.trades:
            entry_d = t.entry_date.strftime('%Y-%m-%d')
            exit_d = t.exit_date.strftime('%Y-%m-%d') if t.exit_date else "OPEN"
            print(f"{entry_d:<12} | {exit_d:<12} | {t.entry_price:<8.2f} | {t.exit_price:<8.2f} | {t.pnl_pct:>5.2f}% | {t.reason}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
