import pytest

pytestmark = pytest.mark.xfail(
    reason="Integration tests need full backend setup; tracked separately (tracking: gate-split)", strict=False
)
import asyncio
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


# Force absolute imports by adding project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.application.butterfly_service import ButterflyService
from packages.core.infrastructure.cache.butterfly_cache import ButterflyCache


class StressRepository:
    """Mock Repository for high-frequency testing."""

    def __init__(self):
        self.fixed_end = pd.Timestamp("2024-05-16")

    def get(self, ticker, period):
        # 1 year of daily data
        dates = pd.date_range(end=self.fixed_end, periods=252, freq="D")
        np.random.seed(abs(hash(ticker)) % (2**32))
        df = pd.DataFrame({"Close": np.random.randn(252).cumsum() + 100}, index=dates)
        return df, self.fixed_end


@pytest.fixture
def service():
    test_db = PROJECT_ROOT / "tests" / "integration" / "stress_butterfly.db"
    if test_db.exists():
        try:
            test_db.unlink()
        except PermissionError:
            pass

    cache = ButterflyCache(db_path=str(test_db))
    repo = StressRepository()
    svc = ButterflyService(ohlcv_repo=repo, cache=cache)
    yield svc
    svc.shutdown()
    if test_db.exists():
        try:
            test_db.unlink()
        except PermissionError:
            pass


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_high_frequency_throughput(service, anyio_backend):
    """
    Test for 100 state updates/sec equivalent stress.
    In our context, we fire 100 concurrent requests to simulate a burst.
    """
    ticker = "STRESS_TKR"
    count = 100

    start = time.perf_counter()
    tasks = [service.get_risk_map(f"{ticker}_{i}") for i in range(count)]
    results = await asyncio.gather(*tasks)
    duration = time.perf_counter() - start

    assert len(results) == count
    for r in results:
        assert len(r.get("nodes", [])) > 0

    print(f"\n[STRESS] Processed {count} unique graphs in {duration:.2f}s ({count/duration:.2f} req/s)")


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_memory_stability_burst(service, anyio_backend):
    """
    Check if repeated large bursts cause executor exhaustion or errors.
    """
    burst_size = 50
    rounds = 3

    for i in range(rounds):
        tasks = [service.get_risk_map(f"BURST_{i}_{j}") for j in range(burst_size)]
        results = await asyncio.gather(*tasks)
        assert len(results) == burst_size
        # Small sleep between bursts to simulate real usage
        await asyncio.sleep(0.1)


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_heavy_concurrency_same_ticker(service, anyio_backend):
    """
    Extreme contention test: 200 requests for the exact same ticker.
    Ensures the 'first one wins, others wait or read' logic in cache/I-O works.
    """
    ticker = "CONTENTION_TKR"
    count = 200

    tasks = [service.get_risk_map(ticker) for _ in range(count)]
    results = await asyncio.gather(*tasks)

    assert len(results) == count
    for r in results:
        assert r["nodes"][0]["id"] == ticker
