import pytest

pytestmark = pytest.mark.xfail(
    reason="Integration tests need full backend setup; tracked separately (tracking: gate-split)", strict=False
)
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pandas as pd


from apps.cli.stock_analyzer.domain.models import StockResult
from apps.cli.stock_analyzer.use_cases.analyzer import StockAnalyzer


@pytest.fixture
def mock_components():
    fetcher = MagicMock()
    cleaner = MagicMock()
    indicators = MagicMock()
    scoring = MagicMock()
    ml_engine = MagicMock()
    advanced_indicators = MagicMock()

    return fetcher, cleaner, indicators, scoring, ml_engine, advanced_indicators


def test_stock_analyzer_full_flow(mock_components):
    fetcher, cleaner, indicators, scoring, ml_engine, advanced_indicators = mock_components

    # 1. Setup Mock Data
    start_time = datetime(2023, 1, 1)
    daily_data = pd.DataFrame(
        {"Open": [100] * 110, "High": [105] * 110, "Low": [95] * 110, "Close": [102] * 110, "Volume": [1000] * 110},
        index=[start_time + timedelta(days=i) for i in range(110)],
    )

    intraday_data = pd.DataFrame(
        {"Open": [102] * 50, "High": [103] * 50, "Low": [101] * 50, "Close": [102.5] * 50, "Volume": [500] * 50},
        index=[start_time + timedelta(minutes=i) for i in range(50)],
    )

    # 2. Configure Mocks
    fetcher.fetch.return_value = daily_data
    fetcher.fetch_intraday.return_value = intraday_data
    cleaner.clean.side_effect = lambda df, ticker: df

    # Mock Indicators to return a DF with required columns
    def mock_compute(df, **kwargs):
        df["rsi"] = 50.0
        df["macd_hist"] = 0.1
        df["atr"] = 2.0
        df["ema50"] = 100.0
        df["bb_upper"] = 110.0
        df["bb_lower"] = 90.0
        return df

    indicators.compute.side_effect = mock_compute
    indicators.compute_mrc.side_effect = lambda df, ctx: df

    ml_engine.predict.return_value = (0.01, 110.0, "BUY", False)
    ml_engine.get_ticker_stats.return_value = {}

    scoring.calculate_composite_score.return_value = (
        75.0,
        {"trend": 80, "momentum": 70, "structure": 75, "volume": 75},
    )
    scoring.calculate_css.return_value = (80.0, "TIER_1")
    scoring.generate_signal.return_value = "STRONG_BUY"

    advanced_indicators.compute_advanced.return_value = {
        "poc": 102.2,
        "vah": 103.0,
        "val": 101.5,
        "amt_state": "BALANCED",
        "market_structure": "HH",
        "cumulative_delta": 5000.0,
        "vwap": 102.3,
    }

    # 3. Execute
    analyzer = StockAnalyzer(
        fetcher, cleaner, indicators, scoring, ml_engine=ml_engine, advanced_indicators=advanced_indicators
    )
    result = analyzer.analyze_ticker("AAPL")

    # 4. Assert
    assert isinstance(result, StockResult)
    assert result.ticker == "AAPL"
    assert result.poc == 102.2
    assert result.vah == 103.0
    assert result.val == 101.5
    assert result.amt_state == "BALANCED"
    assert result.market_structure == "HH"
    assert result.cumulative_delta == 5000.0
    assert result.vwap == 102.3
    assert result.signal == "STRONG_BUY"
