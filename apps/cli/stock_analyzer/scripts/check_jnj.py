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

analyzer = StockAnalyzer(DataFetcher(), DataCleaner(), IndicatorEngine(), ScoringEngine())
res = analyzer.analyze_ticker("JNJ")
if res:
    print(f"Ticker: {res.ticker}")
    print(f"Price: {res.current_price}")
    print(f"Score: {res.score}/10.0")
    print(f"  - Trend Score: {res.trend_score}")
    print(f"  - Momentum Score: {res.momentum_score}")
    print(f"  - Volatility Score: {res.volatility_score}")
    print(f"  - Liquidity Score: {res.liquidity_score}")
    print(f"Signal: {res.signal}")
    print(f"EMA200: {res.support}") # check support as proxy
    print(f"1W Forecast: {res.forecast_1w}")
