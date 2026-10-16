import pytest

pytestmark = pytest.mark.xfail(
    reason="Integration tests need full backend setup; tracked separately (tracking: gate-split)", strict=False
)
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# Force absolute imports by adding project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.application.butterfly_service import ButterflyService
from packages.core.infrastructure.cache.butterfly_cache import ButterflyCache


# Mock Repository to control data availability
class MockRepository:
    def __init__(self):
        self.fixed_end = pd.Timestamp("2024-05-16")
        self.should_fail = False

    def get(self, ticker, period):
        if self.should_fail:
            return None, self.fixed_end

        # Return realistic-ish 1 year of random data
        dates = pd.date_range(end=self.fixed_end, periods=252, freq="D")
        np.random.seed(hash(ticker) % 2**32)
        base = np.linspace(0, 10, 252)
        df = pd.DataFrame(
            {
                "Close": base + np.random.randn(252) + 100,
            },
            index=dates,
        )
        return df, self.fixed_end


@pytest.fixture
def service():
    """Setup ButterflyService with a clean temporary cache."""
    test_db = PROJECT_ROOT / "tests" / "integration" / "test_butterfly_diag.db"
    if test_db.exists():
        try:
            test_db.unlink()
        except PermissionError:
            pass

    cache = ButterflyCache(db_path=str(test_db))
    repo = MockRepository()
    svc = ButterflyService(ohlcv_repo=repo, cache=cache)
    yield svc, repo
    svc.shutdown()
    if test_db.exists():
        try:
            test_db.unlink()
        except PermissionError:
            pass


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_butterfly_diagnostics_success(service, caplog, anyio_backend):
    """Verify diagnostic logging and metadata for a successful request."""
    svc, repo = service
    ticker = "AAPL"

    with caplog.at_level(logging.INFO, logger="butterfly.service"):
        res = await svc.get_risk_map(ticker)

    # 1. Verify Response Status
    assert res["status"] == "success"
    assert "metadata" in res

    # 2. Verify Diagnostic Logs
    log_messages = [record.message for record in caplog.records]
    assert any(f"graph request: {ticker}" in msg for msg in log_messages)
    assert any("correlation started" in msg for msg in log_messages)
    assert any("nodes generated:" in msg for msg in log_messages)
    assert any("edges generated:" in msg for msg in log_messages)
    assert any("response sent (cache miss):" in msg for msg in log_messages)

    # 3. Verify Metadata matches logs
    node_log = [msg for msg in log_messages if "nodes generated:" in msg][0]
    edge_log = [msg for msg in log_messages if "edges generated:" in msg][0]

    # Extract counts from log strings (e.g. "[Butterfly] nodes generated: 7")
    logged_node_count = int(node_log.split(":")[-1].strip())
    logged_edge_count = int(edge_log.split(":")[-1].strip())

    assert res["metadata"]["final_node_count"] == logged_node_count
    assert res["metadata"]["final_edge_count"] == logged_edge_count
    assert len(res["nodes"]) == logged_node_count
    assert len(res["edges"]) == logged_edge_count

    assert "original_node_count" in res["metadata"]
    assert "original_edge_count" in res["metadata"]
    assert "is_trimmed" in res["metadata"]
    assert isinstance(res["metadata"]["is_trimmed"], bool)


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_butterfly_diagnostics_fallback(service, caplog, anyio_backend):
    """Verify fallback response and logging for insufficient data."""
    svc, repo = service
    ticker = "UNKNOWN"
    repo.should_fail = True

    with caplog.at_level(logging.WARNING, logger="butterfly.service"):
        res = await svc.get_risk_map(ticker)

    # 1. Verify Fallback Status
    assert res["status"] == "insufficient_data"
    assert "message" in res
    assert res["message"] == "Not enough correlation data available"
    assert res["nodes"] == []
    assert res["edges"] == []

    # 2. Verify Warning Logs
    log_messages = [record.message for record in caplog.records]
    assert any(f"{ticker} not in returns_map. Insufficient data." in msg for msg in log_messages)


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_butterfly_diagnostics_cache_hit_logs(service, caplog, anyio_backend):
    """Verify logs reflect cache status."""
    svc, repo = service
    ticker = "AAPL"

    # First request - Cache Miss
    await svc.get_risk_map(ticker)
    caplog.clear()

    # Second request - Cache Hit
    with caplog.at_level(logging.INFO, logger="butterfly.service"):
        res = await svc.get_risk_map(ticker)

    assert res["status"] == "success"
    log_messages = [record.message for record in caplog.records]
    assert any("cache hit" in msg for msg in log_messages)
    assert any("response sent (cache hit):" in msg for msg in log_messages)
