import json
import logging
from datetime import datetime

from apps.cli.stock_analyzer.adapters.cleaner import DataCleaner
from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
from apps.cli.stock_analyzer.adapters.indicators import IndicatorEngine
from apps.cli.stock_analyzer.domain.config import AppConfig
from apps.cli.stock_analyzer.domain.scoring import ScoringEngine
from apps.cli.stock_analyzer.use_cases.backtester import Backtester


def run_mega_backtest():
    logging.basicConfig(level=logging.ERROR)

    # Tickers setup
    idx_tickers = ["BBCA.JK", "ADRO.JK", "TLKM.JK", "BMRI.JK", "ASII.JK"]
    us_tickers = ["JNJ", "PUBM", "NVDA", "AAPL", "MSFT", "GOOGL", "AMD", "NFLX", "PLTR"]
    crypto_tickers = ["BTC-USD", "ETH-USD", "SOL-USD"]

    all_tickers = idx_tickers + us_tickers + crypto_tickers

    # Components
    fetcher = DataFetcher()
    cleaner = DataCleaner()
    indicators = IndicatorEngine()
    scoring = ScoringEngine()

    # Setting threshold 7.0 for swing trading
    config = AppConfig.load()
    config.buy_threshold = 7.0

    backtester = Backtester(fetcher, cleaner, indicators, scoring, config)

    results_summary = []

    print("Starting MEGA SWING BACKTEST (Holding Period ~1 Week)")
    print(f"Strategy: Threshold {config.buy_threshold}, Timeframe: 4h, Period: 1y")

    for ticker in all_tickers:
        print(f"Testing {ticker}...", end=" ", flush=True)
        try:
            # Period 1y to have enough 4h bars
            result = backtester.run(ticker, period="1y", interval="4h")

            summary = {
                "ticker": ticker,
                "total_trades": result.total_trades,
                "win_rate": round(result.win_rate, 2),
                "total_return": round(result.total_return_pct, 2),
                "avg_return": round(result.avg_return_pct, 2),
                "max_drawdown": round(result.max_drawdown_pct, 2),
                "type": "IDX" if ticker.endswith(".JK") else ("Crypto" if "-USD" in ticker else "US")
            }
            results_summary.append(summary)
            print(f"Done. Trades: {summary['total_trades']}, Return: {summary['total_return']}%")

        except Exception as e:
            print(f"Failed: {e}")

    # Save results
    output_file = f"mega_backtest_weekly_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results_summary, f, indent=4)

    print(f"\nSaved results to {output_file}")

    # Leaderboard
    print("\n=== TOP 5 SWING PERFORMERS ===")
    top_5 = sorted(results_summary, key=lambda x: x['total_return'], reverse=True)[:5]
    for i, res in enumerate(top_5, 1):
        print(f"{i}. {res['ticker']} ({res['type']}): {res['total_return']}% return, {res['win_rate']}% win rate, {res['total_trades']} trades")

if __name__ == "__main__":
    run_mega_backtest()
