import pytest

pytestmark = pytest.mark.xfail(
    reason="Integration tests need full backend setup; tracked separately (tracking: gate-split)", strict=False
)
import asyncio
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# Force absolute imports by adding project root to sys.path
# This test is expected to be in project_root/tests/integration/test_butterfly_stability.py
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.application.butterfly_service import ButterflyService
from packages.core.infrastructure.cache.butterfly_cache import ButterflyCache


# Mock Repository to avoid DB dependencies
class MockRepository:
    def __init__(self):
        # Use a fixed end date so all tickers align their indices
        self.fixed_end = pd.Timestamp("2024-05-16")

    def get(self, ticker, period):
        # Return realistic-ish 1 year of random data
        dates = pd.date_range(end=self.fixed_end, periods=252, freq="D")
        # Ensure we have some correlation by using a base trend
        np.random.seed(hash(ticker) % 2**32)  # Deterministic for same ticker
        base = np.linspace(0, 10, 252)
        df = pd.DataFrame(
            {
                "Open": base + np.random.randn(252) + 100,
                "High": base + np.random.randn(252) + 105,
                "Low": base + np.random.randn(252) + 95,
                "Close": base + np.random.randn(252) + 100,
                "Volume": np.random.randint(1000, 10000, 252),
            },
            index=dates,
        )
        # Return tuple matching PostgresOHLCVRepository.get signature: (df, fetched_at)
        return df, self.fixed_end


@pytest.fixture
def service():
    """Setup ButterflyService with a clean temporary cache."""
    test_db = PROJECT_ROOT / "tests" / "integration" / "test_butterfly_stability.db"
    if test_db.exists():
        try:
            test_db.unlink()
        except PermissionError:
            pass

    cache = ButterflyCache(db_path=str(test_db))
    repo = MockRepository()
    svc = ButterflyService(ohlcv_repo=repo, cache=cache)
    yield svc
    svc.shutdown()
    # Cleanup after tests
    if test_db.exists():
        try:
            test_db.unlink()
        except PermissionError:
            pass


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_butterfly_cache_contention(service, anyio_backend):
    """
    Fire multiple concurrent requests for the same ticker.
    This tests that the async/executor pattern handles multiple simultaneous
    cache misses and subsequent writes without crashing or deadlocking.
    """
    ticker = "AAPL"
    # Fire 20 concurrent requests
    tasks = [service.get_risk_map(ticker) for _ in range(20)]
    results = await asyncio.gather(*tasks)

    assert len(results) == 20
    for res in results:
        assert "nodes" in res
        assert len(res["nodes"]) > 0, f"Expected nodes for {ticker}, got empty list. Metadata: {res.get('metadata')}"
        assert "edges" in res
        assert res["nodes"][0]["id"] == ticker
        assert "metadata" in res

    # Verify cache actually has the data now
    final_res = await service.get_risk_map(ticker)
    assert final_res["nodes"][0]["id"] == ticker


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_butterfly_parallel_different_tickers(service, anyio_backend):
    """
    Fire requests for different tickers simultaneously.
    Ensures data isolation and that the executors can handle parallel loads.
    """
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    tasks = [service.get_risk_map(t) for t in tickers]
    results = await asyncio.gather(*tasks)

    assert len(results) == len(tickers)
    for i, res in enumerate(results):
        assert len(res["nodes"]) > 0, f"Expected nodes for {tickers[i]}, got empty list"
        # Verify result belongs to the requested ticker
        assert res["nodes"][0]["id"] == tickers[i]

        # Verify no data leakage (other tickers shouldn't be the target)
        other_tickers = set(tickers) - {tickers[i]}
        assert res["nodes"][0]["id"] not in other_tickers


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_butterfly_schema_validation(service, anyio_backend):
    """Verify that the response matches the expected schema exactly."""
    ticker = "BTC-USD"
    res = await service.get_risk_map(ticker)

    assert len(res["nodes"]) > 0
    # Basic schema check
    assert isinstance(res["nodes"], list)
    assert isinstance(res["edges"], list)
    assert isinstance(res["metadata"], dict)

    node = res["nodes"][0]
    expected_keys = {"id", "label", "correlation", "description", "impact_level"}
    assert all(key in node for key in expected_keys)

    if len(res["edges"]) > 0:
        edge = res["edges"][0]
        expected_keys = {"source", "target", "weight"}
        assert all(key in edge for key in expected_keys)


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_butterfly_trimming_logic(service, anyio_backend):
    """Verify that max_nodes and max_edges constraints are respected."""
    ticker = "ETH-USD"
    # Use very small limits to force trimming
    max_nodes = 3
    max_edges = 5
    res = await service.get_risk_map(ticker, max_nodes=max_nodes, max_edges=max_edges)

    assert len(res["nodes"]) > 0
    assert len(res["nodes"]) <= max_nodes
    assert len(res["edges"]) <= max_edges
    assert "is_trimmed" in res["metadata"]
    assert res["metadata"]["is_trimmed"] is True
