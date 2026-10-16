import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
# Find the project root (finance-tracker/)
_P = _HERE.parent
while _P.name != "finance-tracker" and _P.parent != _P:
    if (_P / "packages").exists() and (_P / "apps").exists():
        break
    _P = _P.parent
_PROJECT_ROOT = str(_P)
_APPS_DIR = str(_P / "apps")
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import argparse

from apps.cli.stock_analyzer.adapters.cleaner import DataCleaner
from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
from apps.cli.stock_analyzer.adapters.fred_fetcher import FREDFetcher
from apps.cli.stock_analyzer.adapters.indicators import IndicatorEngine
from apps.cli.stock_analyzer.domain.config import AppConfig
from apps.cli.stock_analyzer.domain.scoring import ScoringEngine
from apps.cli.stock_analyzer.infrastructure.macro_repository import MacroRepository
from apps.cli.stock_analyzer.infrastructure.tui import MarketAnalyzerApp
from apps.cli.stock_analyzer.use_cases.analyzer import StockAnalyzer


def quick_analyze(ticker):
    print(f"--- Quick Analysis: {ticker} ---")
    config = AppConfig.load()

    # Use MacroRepository for centralized and synchronized fetching
    print("Initializing Macro Repository...")
    macro_repo = MacroRepository(FREDFetcher(config), DataFetcher())
    macro_repo.initialize()

    macro_context = macro_repo.get_fred_context()
    dxy_df = macro_repo.get_dxy()

    if macro_context.get('is_stale'):
        print("[!] Warning: Using stale FRED macro data.")
    print(f"Market Regime: {macro_context['regime']}")

    analyzer = StockAnalyzer(DataFetcher(), DataCleaner(), IndicatorEngine(), ScoringEngine(), config, macro_context, macro_repo=macro_repo)
    res = analyzer.analyze_ticker(ticker, dxy_df=dxy_df)
    if res:
        print(f"Ticker: {res.ticker}")
        print(f"Price:  {res.current_price}")
        print(f"Score:  {res.score}/10.0")
        print(f"Signal: {res.signal.value}")
        print("--- Strategy ---")
        print(f"Support:    {res.support}")
        print(f"Resistance: {res.resistance}")
        print(f"Stop Loss:  {res.stop_loss}")
        print(f"Take Profit: {res.take_profit}")
        print(f"Forecast 1W: {res.forecast_1w*100:+.2f}%")
        print(f"Forecast 1M: {res.forecast_1m*100:+.2f}%")
        print("--- Risk & Expectancy ---")
        print(f"Expectancy: {res.expectancy}")
        print(f"Win Rate:   {res.win_rate*100}%")
        print(f"RR Ratio:   {res.risk_reward_ratio}")
        print(f"Kelly %:    {res.kelly_fraction*100}%")
        print(f"Pos Size:   {res.position_size} units")
        print("--- Macro ---")
        print(f"CSS:    {res.css} ({res.css_tier})")
        print(f"CSI:    {res.csi} (Consumer Sentiment)")
        print(f"DCDS:   {res.dcds}")

        print(f"MRZG:   {res.mrzg}")
        print("--- ML Sniper ---")
        print(f"Signal: {res.ml_signal}")
        print(f"Prob:   {res.ml_prob:.3f}")
        print(f"Sniper: {'YES' if res.is_selective else 'NO'}")
    else:
        print("Failed to fetch or analyze data.")

def main():
    parser = argparse.ArgumentParser(description="Gacor Stock Analyzer CLI")
    parser.add_argument("--ticker", type=str, help="Quick analyze a specific ticker without TUI")
    parser.add_argument("--list", action="store_true", help="Show all tickers in list.txt")

    args = parser.parse_args()

    if args.ticker:
        quick_analyze(args.ticker.upper())
    elif args.list:
        try:
            list_path = Path(__file__).resolve().parent / "list.txt"
            with open(list_path) as f:
                print(f.read())
        except FileNotFoundError:
            print("list.txt not found.")
    else:
        # Default to TUI mode
        import os
        if not sys.stdin.isatty() or os.environ.get("TERM") == "dumb":
            print("MarketAnalyzerApp TUI mode (Skipped in non-TTY/headless environment)")
            return
        app = MarketAnalyzerApp()
        app.run()

if __name__ == "__main__":
    main()
