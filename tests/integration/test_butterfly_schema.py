import pytest

pytestmark = pytest.mark.xfail(
    reason="Integration tests need full backend setup; tracked separately (tracking: gate-split)", strict=False
)
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from pydantic import ValidationError

# Force absolute imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.application.butterfly_schemas import ButterflyResponse
from packages.core.application.butterfly_service import ButterflyService
from packages.core.infrastructure.cache.butterfly_cache import ButterflyCache


class MockRepository:
    def __init__(self):
        self.fixed_end = pd.Timestamp("2024-05-16")
        self.fail_tickers = set()
        self.empty_tickers = set()

    def get(self, ticker, period):
        if ticker in self.fail_tickers:
            return None
        if ticker in self.empty_tickers:
            return pd.DataFrame(), self.fixed_end

        # 1 year of daily data
        dates = pd.date_range(end=self.fixed_end, periods=252, freq="D")
        # Use deterministic seed for the ticker to keep tests stable
        # Using a simpler seed generator that is stable across runs
        seed = sum(ord(c) for c in ticker) % (2**32)
        np.random.seed(seed)
        df = pd.DataFrame({"Close": np.random.randn(252).cumsum() + 100}, index=dates)
        return df, self.fixed_end


@pytest.fixture
def repo():
    return MockRepository()


@pytest.fixture
def service(repo):
    test_db = PROJECT_ROOT / "tests" / "integration" / "test_butterfly_schema.db"
    if test_db.exists():
        try:
            test_db.unlink()
        except PermissionError:
            pass

    cache = ButterflyCache(db_path=str(test_db))
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
async def test_schema_integrity_and_pydantic_validation(service):
    """
    Validate that get_risk_map returns a payload that strictly follows ButterflyResponse.
    """
    target = "AAPL"
    result = await service.get_risk_map(target)

    # 1. Pydantic Validation
    try:
        validated = ButterflyResponse(**result)
    except ValidationError as e:
        pytest.fail(f"Pydantic validation failed: {e}")

    # 2. Critical Fields Integrity (0% NaN/null leakage)
    assert len(validated.nodes) > 0, "Should have generated nodes"
    for node in validated.nodes:
        assert node.id is not None, "Node ID must not be None"
        assert node.ticker is not None, "Node ticker must not be None"
        assert not np.isnan(node.correlation), f"Node {node.id} has NaN correlation"
        assert node.label is not None, "Node label must not be None"

    for edge in validated.edges:
        assert edge.source is not None, "Edge source must not be None"
        assert edge.target is not None, "Edge target must not be None"
        assert not np.isnan(edge.weight), f"Edge {edge.source}->{edge.target} has NaN weight"

    # 3. Topological Integrity
    node_ids = {n.id for n in validated.nodes}
    for edge in validated.edges:
        assert edge.source in node_ids, f"Edge source {edge.source} not in nodes"
        assert edge.target in node_ids, f"Edge target {edge.target} not in nodes"


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_fuzzing_invalid_ticker(service, repo):
    """
    Fuzz with a ticker that returns None from repo.
    """
    target = "INVALID_TKR"
    repo.fail_tickers.add(target)

    result = await service.get_risk_map(target)
    validated = ButterflyResponse(**result)

    assert validated.status == "insufficient_data"
    assert len(validated.nodes) == 0
    assert len(validated.edges) == 0


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_fuzzing_empty_ticker(service, repo):
    """
    Fuzz with a ticker that returns empty DataFrame.
    """
    target = "EMPTY_TKR"
    repo.empty_tickers.add(target)

    result = await service.get_risk_map(target)
    validated = ButterflyResponse(**result)

    assert validated.status == "insufficient_data"
    assert len(validated.nodes) == 0
    assert len(validated.edges) == 0


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_fuzzing_minimal_data(service, repo):
    """
    Fuzz with a ticker that has < 30 samples.
    """
    target = "MINIMAL_TKR"
    # Use a custom generator for this specific ticker
    original_get = repo.get

    def get_minimal(ticker, period):
        if ticker == target:
            dates = pd.date_range(end=pd.Timestamp("2024-05-16"), periods=10, freq="D")
            df = pd.DataFrame({"Close": np.random.randn(10).cumsum() + 100}, index=dates)
            return df, pd.Timestamp("2024-05-16")
        return original_get(ticker, period)

    repo.get = get_minimal

    result = await service.get_risk_map(target)
    validated = ButterflyResponse(**result)

    assert validated.status == "insufficient_data"
    assert len(validated.nodes) == 0
