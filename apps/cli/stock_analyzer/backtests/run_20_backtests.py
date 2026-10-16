import logging
import sys
from pathlib import Path

# Add root to sys.path
ROOT = Path(__file__).parent.parent.resolve()
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from apps.cli.stock_analyzer.adapters.cleaner import DataCleaner
from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
from apps.cli.stock_analyzer.adapters.indicators import IndicatorEngine
from apps.cli.stock_analyzer.domain.config import AppConfig
from apps.cli.stock_analyzer.domain.scoring import ScoringEngine
from apps.cli.stock_analyzer.use_cases.backtester import Backtester


def run_20_backtests():
    logging.basicConfig(level=logging.ERROR)

    # 20 Diverse Tickers
    tickers = [
        "BBCA.JK", "BMRI.JK", "TLKM.JK", "ASII.JK", "ADRO.JK", "GOTO.JK", "UNVR.JK", # IDX (7)
        "AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "AMD", "NFLX",      # US (9)
        "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"                                  # Crypto (4)
    ]

    # Components
    fetcher = DataFetcher()
    cleaner = DataCleaner()
    indicators = IndicatorEngine()
    scoring = ScoringEngine()
    config = AppConfig.load()

    backtester = Backtester(fetcher, cleaner, indicators, scoring, config)
    results_summary = []

    print("=== ML SNIPER MEGA BACKTEST (20 TICKERS) ===")
    print("Strategy: XGBoost Sniper, Threshold: 0.85, Horizon: 5-10 Days")
    print("Period: 2y, Interval: 1d\n")

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/20] Testing {ticker:10}...", end=" ", flush=True)
        try:
            result = backtester.run(ticker, period="2y", interval="1d")

            summary = {
                "ticker": ticker,
                "trades": result.total_trades,
                "win_rate": f"{result.win_rate:.1f}%",
                "total_return": f"{result.total_return_pct:+.2f}%",
                "avg_return": f"{result.avg_return_pct:+.2f}%",
                "max_dd": f"{result.max_drawdown_pct:.1f}%",
                "raw_return": result.total_return_pct
            }
            results_summary.append(summary)
            print(f"DONE. Trades: {summary['trades']:3} | Win: {summary['win_rate']:6} | Ret: {summary['total_return']}")

        except Exception as e:
            print(f"FAILED: {e}")

    # Print Leaderboard
    print("\n" + "="*50)
    print("TOP 5 PERFORMERS (ML SNIPER)")
    print("="*50)
    top_5 = sorted(results_summary, key=lambda x: x['raw_return'], reverse=True)[:5]
    for i, res in enumerate(top_5, 1):
        print(f"{i}. {res['ticker']:10} | Ret: {res['total_return']} | Win: {res['win_rate']} | Trades: {res['trades']}")
    print("="*50)

if __name__ == "__main__":
    run_20_backtests()
