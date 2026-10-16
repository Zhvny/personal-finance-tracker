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

import os

# Menambahkan direktori root ke path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apps.cli.stock_analyzer.adapters.cleaner import DataCleaner
from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
from apps.cli.stock_analyzer.adapters.indicators import IndicatorEngine
from apps.cli.stock_analyzer.domain.scoring import ScoringEngine
from apps.cli.stock_analyzer.use_cases.analyzer import StockAnalyzer


def analyze_ticker_quick(ticker):
    analyzer = StockAnalyzer(
        DataFetcher(), DataCleaner(), IndicatorEngine(), ScoringEngine()
    )
    result = analyzer.analyze_ticker(ticker)
    if result:
        print(f"\n=== Technical Analysis for {ticker} ===")
        print(f"Signal: {result.signal.value}")
        print(f"Score: {result.score:.2f}")
        print(f"  - Trend Score: {result.trend_score:.2f}")
        print(f"  - Momentum Score: {result.momentum_score:.2f}")
        print(f"  - Volatility Score: {result.volatility_score:.2f}")
        print("\nPrice Levels:")
        print(f"  - Current Price (Entry): {result.entry}")
        print(f"  - Support: {result.support}")
        print(f"  - Resistance: {result.resistance}")
        print(f"  - Stop Loss: {result.stop_loss}")
        print(f"  - Take Profit: {result.take_profit}")
    else:
        print(f"Failed to analyze {ticker}")

if __name__ == "__main__":
    analyze_ticker_quick("PUBM")
