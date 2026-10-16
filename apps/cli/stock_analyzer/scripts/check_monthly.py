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

sys.path.append(os.getcwd())
from apps.cli.stock_analyzer.adapters.cleaner import DataCleaner
from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
from apps.cli.stock_analyzer.adapters.indicators import IndicatorEngine
from apps.cli.stock_analyzer.domain.scoring import ScoringEngine
from apps.cli.stock_analyzer.use_cases.analyzer import StockAnalyzer

tickers = ["AMZN", "JNJ", "GC=F", "MSTR", "CIFR", "RTX"]
analyzer = StockAnalyzer(DataFetcher(), DataCleaner(), IndicatorEngine(), ScoringEngine())

print(f"{'Ticker':<10} | {'Price':<10} | {'1W Forecast':<12} | {'1M Forecast':<12} | {'Signal'}")
print("-" * 65)

for t in tickers:
    res = analyzer.analyze_ticker(t)
    if res:
        print(f"{res.ticker:<10} | {res.current_price:<10} | {res.forecast_1w:<12} | {res.forecast_1m:<12} | {res.signal.value}")
