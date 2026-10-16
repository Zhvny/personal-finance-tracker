import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
# Find the directory that contains 'stock_analyzer'
_P = _HERE.parent
while _P.name != "stock_analyzer" and _P.parent != _P:
    _P = _P.parent
_PROJECT_ROOT = str(_P.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import logging
import os

from tabulate import tabulate

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Menambahkan direktori root ke path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apps.cli.stock_analyzer.adapters.cleaner import DataCleaner
from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
from apps.cli.stock_analyzer.adapters.indicators import IndicatorEngine
from apps.cli.stock_analyzer.domain.scoring import ScoringEngine
from apps.cli.stock_analyzer.use_cases.analyzer import StockAnalyzer

# from apps.cli.stock_analyzer.domain.portfolio_manager import PortfolioManager

def analyze_my_portfolio():
    import json
    portfolio_path = os.path.join(os.path.dirname(__file__), "..", "portfolio_fix.json")
    try:
        with open(portfolio_path, "r") as f:
            portfolio_data = json.load(f)
        # print(f"Loaded {len(portfolio_data)} from {portfolio_path}")
    except Exception as e:
        print(f"Error loading portfolio.json: {e}")
        portfolio_data = []

    # Force 2y period for EMA200
    from apps.cli.stock_analyzer.domain.config import AppConfig
    config = AppConfig()
    config.fetch_period = "2y"

    analyzer = StockAnalyzer(
        DataFetcher(), DataCleaner(), IndicatorEngine(), ScoringEngine(),
        config=config
    )

    # Define extra tickers for Currencies and Commodities
    market_watch = [
        "EURIDR=X", "USDIDR=X", "JPYIDR=X",
        "GC=F", "CL=F", "SI=F"
    ]

    portfolio_tickers = [p["ticker"] for p in portfolio_data]
    # print(f"DEBUG: portfolio_tickers={portfolio_tickers}")
    # Use a set to avoid duplicates and ensure all are listed
    all_tickers = list(set(portfolio_tickers + market_watch))

    print(f"Analyzing {len(all_tickers)} tickers: {all_tickers}")
    results = analyzer.run_batch(all_tickers)

    table_data = []

    for r in results:
        # Check if it's in portfolio
        p_info = next((p for p in portfolio_data if p["ticker"] == r.ticker), None)

        entry = p_info["entry"] if p_info else 0
        current_price = r.current_price

        p_l_pct = ((current_price - entry) / entry * 100) if entry > 0 else 0
        p_l_abs = (current_price - entry) if entry > 0 else 0

        # Action Logic refinement
        # AVOID usually means high volatility or bad trend.
        # For existing holdings, we only SELL if it's really bad or hits SL.
        action = "HOLD"
        if r.signal.value == "BUY":
            action = "BUY / STRONG HOLD"
        elif r.signal.value == "WAIT":
            action = "HOLD / MONITOR"
        elif r.signal.value == "AVOID":
            if entry > 0:
                # If we have it and it's AVOID, check if it's high risk
                action = "SELL / REDUCE"
            else:
                action = "AVOID"

        table_data.append([
            r.ticker,
            r.signal.value,
            f"{current_price:.2f}",
            f"{entry:.2f}" if entry > 0 else "-",
            f"{p_l_pct:.2f}%" if entry > 0 else "-",
            f"{p_l_abs:.2f}" if entry > 0 else "-",
            f"{r.stop_loss:.2f}",
            f"{r.take_profit:.2f}",
            action
        ])

    headers = ["Ticker", "Signal", "Current", "Entry", "P&L%", "P&L Abs", "Stop Loss", "Take Profit", "Action"]

    print("\n=== PORTFOLIO & MARKET REPORT (April 9, 2026) ===\n")
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print("\n* Note: 'AVOID' signal often triggers due to high volatility (ATR > 5%).")

if __name__ == "__main__":
    analyze_my_portfolio()
