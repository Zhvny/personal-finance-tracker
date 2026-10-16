import pytest

pytestmark = pytest.mark.xfail(
    reason="Integration tests need full backend setup; tracked separately (tracking: gate-split)", strict=False
)
import os
import sys
from pathlib import Path

# Add apps and root directory to sys.path to allow imports of stock_analyzer and packages
project_root = str(Path(__file__).resolve().parent.parent.parent)
apps_path = os.path.join(project_root, "apps")
if project_root not in sys.path:
    sys.path.append(project_root)
if apps_path not in sys.path:
    sys.path.append(apps_path)

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from stock_analyzer.adapters.cache import DataCache
from stock_analyzer.adapters.cleaner import DataCleaner
from stock_analyzer.adapters.fetcher import DataFetcher
from stock_analyzer.adapters.fred_fetcher import FREDFetcher
from stock_analyzer.adapters.indicators import IndicatorEngine
from stock_analyzer.domain.scoring import ScoringEngine
from stock_analyzer.infrastructure.macro_repository import MacroRepository
from stock_analyzer.use_cases.analyzer import StockAnalyzer

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FailureSimulator:
    """Context manager to simulate various DXY fetch failure states."""

    def __init__(self, fetcher: DataFetcher):
        self.fetcher = fetcher
        self._original_fetch = fetcher.fetch
        self.mode = "normal"  # normal, timeout, error, empty, stale, success
        self.exception_to_raise = ValueError("Simulated Fetch Failure")
        self.stale_data = None
        self.patcher = None

    def __enter__(self):
        self.patcher = patch.object(self.fetcher, "fetch", side_effect=self._mock_fetch)
        self.patcher.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.patcher:
            self.patcher.stop()

    def set_mode(self, mode: str, exception=None, stale_data=None):
        self.mode = mode
        if exception:
            self.exception_to_raise = exception
        if stale_data is not None:
            self.stale_data = stale_data

    def _mock_fetch(self, symbol, **kwargs):
        symbol_clean = str(symbol).replace("$", "")
        is_dxy = "DX-Y.NYB" in symbol or symbol_clean.upper() == "DXY"

        if not is_dxy:
            return self._original_fetch(symbol, **kwargs)

        if self.mode == "timeout":
            raise TimeoutError("Simulated Timeout")

        if self.mode == "error":
            raise self.exception_to_raise

        if self.mode == "empty":
            return pd.DataFrame()

        if self.mode == "stale":
            if self.stale_data is not None:
                return self.stale_data
            return pd.DataFrame(
                {
                    "Open": [100.0, 101.0],
                    "High": [100.5, 101.5],
                    "Low": [99.5, 100.5],
                    "Close": [100.0, 101.0],
                    "Volume": [1000, 1100],
                },
                index=pd.date_range(end="2020-01-01", periods=2),
            )

        if self.mode == "success":
            if self.stale_data is not None:
                return self.stale_data
            return pd.DataFrame(
                {
                    "Open": [110.0, 111.0],
                    "High": [110.5, 111.5],
                    "Low": [109.5, 110.5],
                    "Close": [110.0, 111.0],
                    "Volume": [1000, 1100],
                },
                index=pd.date_range(end="2026-05-15", periods=2),
            )

        return self._original_fetch(symbol, **kwargs)


@pytest.fixture
def temp_cache_db(tmp_path):
    """Provides a temporary SQLite database path for DataCache."""
    db_path = tmp_path / "test_cache.db"
    return str(db_path)


@pytest.fixture
def data_fetcher(temp_cache_db):
    """DataFetcher with a temporary cache."""
    cache = DataCache(db_path=temp_cache_db)
    cache.pg_repo = None
    return DataFetcher(cache=cache)


@pytest.fixture
def fred_fetcher():
    """FREDFetcher instance with mocked series fetching."""
    config = MagicMock()
    config.fred_api_key = "dummy"
    fred = FREDFetcher(config)
    # Mock fetch_series to avoid network
    fred.fetch_series = MagicMock(return_value=pd.Series())
    return fred


@pytest.fixture
def macro_repo(fred_fetcher, data_fetcher):
    """MacroRepository using the real data_fetcher (with temp cache) and mock fred."""
    return MacroRepository(fred_fetcher, data_fetcher)


@pytest.fixture
def failure_sim(data_fetcher):
    """FailureSimulator for the data_fetcher."""
    return FailureSimulator(data_fetcher)


@pytest.fixture
def analyzer(data_fetcher, macro_repo):
    """Full StockAnalyzer with real components but mocked/temp data sources."""
    cleaner = DataCleaner()
    indicators = IndicatorEngine()
    scoring = ScoringEngine()
    return StockAnalyzer(
        fetcher=data_fetcher, cleaner=cleaner, indicators=indicators, scoring=scoring, macro_repo=macro_repo
    )


def test_dxy_source_integrity(failure_sim, macro_repo):
    """REQ-1: Source Integrity - Verify DXY data structure and properties."""
    # Setup healthy DXY data
    dates = pd.date_range(end="2026-05-15", periods=10)
    healthy_dxy = pd.DataFrame(
        {
            "Open": np.linspace(100, 105, 10),
            "High": np.linspace(101, 106, 10),
            "Low": np.linspace(99, 104, 10),
            "Close": np.linspace(100, 105, 10),
            "Volume": np.random.randint(100, 1000, 10),
        },
        index=dates,
    )

    with failure_sim:
        failure_sim.set_mode("success", stale_data=healthy_dxy)
        df = macro_repo.get_dxy()

        assert not df.empty, "DXY should not be empty"
        assert all(col in df.columns for col in ["Close", "Open", "High", "Low", "Volume"])
        assert df.index.is_monotonic_increasing, "Index must be monotonic increasing"
        assert not (df == 0).all().any(), "No columns should be all zeros"
        assert len(df) >= 2, "Should have enough data for calculations"


def test_dxy_fred_crosscheck(failure_sim, fred_fetcher, macro_repo):
    """REQ-2: FRED Cross-check - Verify correlation between DXY and FRED Broad Index."""
    # Create synthetic correlated data
    dates = pd.date_range(end="2026-05-15", periods=100)

    # Generate a trend
    trend = np.linspace(100, 110, 100)
    noise = np.random.normal(0, 0.1, 100)

    # Simulate trade weighted dollar (FRED)
    fred_broad = pd.Series(trend + noise, index=dates)

    # Simulate DXY (Yahoo) - highly correlated with FRED Broad
    dxy_data = pd.DataFrame(
        {
            "Open": trend + noise + np.random.normal(0, 0.05, 100),
            "Close": trend + noise + np.random.normal(0, 0.05, 100),
            "High": 120,
            "Low": 90,
            "Volume": 1000,
        },
        index=dates,
    )

    fred_fetcher.fetch_series = MagicMock(
        side_effect=lambda sid, **kwargs: fred_broad if sid == "DTWEXBGS" else pd.Series()
    )

    with failure_sim:
        failure_sim.set_mode("success", stale_data=dxy_data)

        dxy = macro_repo.get_dxy()
        fred_val = fred_fetcher.fetch_series("DTWEXBGS")

        # Calculate daily percentage changes for correlation
        dxy_ret = dxy["Close"].pct_change().dropna()
        fred_ret = fred_val.pct_change().dropna()

        correlation = dxy_ret.corr(fred_ret)

        logger.info(f"DXY vs FRED Correlation: {correlation:.4f}")
        assert correlation > 0.8, f"Correlation too low: {correlation:.4f}"


def test_dxy_failure_simulations(failure_sim, macro_repo, analyzer):
    """REQ-3: Failure Simulations - Ensure system resiliency when DXY is unavailable."""
    # Initialize macro context to move past "NEUTRAL" guard in analyzer
    macro_repo.fred.get_macro_context = MagicMock(
        return_value={
            "regime": "GOLDILOCKS",
            "ycmo": 0.1,
            "rrm": 0.1,
            "lpi": 0.5,
            "icm": 0.0,
            "csi": 75.0,
            "errf_mult": 1.0,
        }
    )
    macro_repo.initialize()

    # Mock ticker data for a commodity (GOLD) to trigger DXY dependency
    dates = pd.date_range(end="2026-05-15", periods=300)

    # Generate realistic-ish trend data for indicators (need > 200 rows for EMA200)
    def generate_ohlcv(start_price):
        prices = start_price + np.cumsum(np.random.normal(0, 1, 300))
        return pd.DataFrame(
            {
                "Open": prices,
                "High": prices + 5,
                "Low": prices - 5,
                "Close": prices,
                "Volume": 10000 + np.random.randint(0, 5000, 300),
                "Adj Close": prices,
            },
            index=dates,
        )

    gold_data = generate_ohlcv(2000)
    spy_data = generate_ohlcv(500)

    # Dummy DXY for cleaning phase if needed
    dummy_dxy = generate_ohlcv(100)

    # Helper to setup ticker fetch
    def mock_fetch_ticker(symbol, **kwargs):
        symbol_clean = str(symbol).replace("$", "")
        is_dxy = "DX-Y.NYB" in symbol or symbol_clean.upper() == "DXY"

        if is_dxy:
            if failure_sim.mode == "empty":
                return pd.DataFrame()
            if failure_sim.mode in ["error", "timeout"]:
                # These should normally be raised by the FailureSimulator's patch on DataFetcher.fetch
                # But if MacroRepository handles exceptions internally, it might return empty DF.
                # We ensure here that if we're in these modes, we simulate the failure.
                if failure_sim.mode == "timeout":
                    raise TimeoutError("Simulated Timeout")
                raise failure_sim.exception_to_raise
            return dummy_dxy

        if "GOLD" in symbol:
            return gold_data
        if "SPY" in symbol:
            return gold_data
        return pd.DataFrame()

    with failure_sim:
        with patch.object(analyzer.fetcher, "fetch", side_effect=mock_fetch_ticker):
            # Case 1: DXY fetch returns empty DataFrame
            failure_sim.set_mode("empty")
            try:
                res = analyzer.analyze_ticker("GOLD")
            except Exception as e:
                logger.error(f"Analyzer crashed on empty DXY: {e}")
                raise

            if res is None:
                logger.warning("Analyzer returned None for GOLD with empty DXY. Possible clean/indicators failure.")

            assert res is not None, "Analyzer should not crash when DXY is empty"
            assert res.dcds is None, "DCDS should be None when DXY missing"

            # Case 2: DXY fetch raises Error
            failure_sim.set_mode("error", exception=RuntimeError("API Limit"))
            res = analyzer.analyze_ticker("GOLD")
            assert res is not None, "Analyzer should not crash when DXY fetch errors"
            assert res.dcds is None, "DCDS should be None when DXY fetch errors"

            # Case 3: DXY fetch timeouts
            failure_sim.set_mode("timeout")
            res = analyzer.analyze_ticker("GOLD")
            assert res is not None, "Analyzer should not crash when DXY timeouts"
            assert res.dcds is None, "DCDS should be None on timeout"


def test_harness_initialization(macro_repo, data_fetcher):
    """Verify that the test harness and fixtures are correctly wired."""
    assert macro_repo.fetcher == data_fetcher
    assert data_fetcher.cache.db_path.endswith("test_cache.db")


def test_failure_simulator_interception(data_fetcher, failure_sim):
    """Verify that the FailureSimulator correctly intercepts DXY calls."""
    # Normal data for DXY
    dxy_data = pd.DataFrame({"Close": [105.0]}, index=pd.date_range("2026-01-01", periods=1))

    with failure_sim:
        # Mode: error
        failure_sim.set_mode("error", exception=RuntimeError("DXY Down"))
        with pytest.raises(RuntimeError, match="DXY Down"):
            data_fetcher.fetch("DX-Y.NYB")

        # Mode: empty
        failure_sim.set_mode("empty")
        df = data_fetcher.fetch("DX-Y.NYB")
        assert df.empty

        # Mode: success
        failure_sim.set_mode("success", stale_data=dxy_data)
        df = data_fetcher.fetch("DX-Y.NYB")
        assert not df.empty
        assert df["Close"].iloc[0] == 105.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
