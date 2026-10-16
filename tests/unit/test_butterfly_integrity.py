from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from packages.core.application.butterfly_schemas import ButterflyResponse
from packages.core.application.butterfly_service import ButterflyService


@pytest.fixture
def mock_repo():
    return MagicMock()

@pytest.fixture
def mock_cache():
    cache = MagicMock()
    cache.get.return_value = None
    return cache

@pytest.fixture
def service(mock_repo, mock_cache):
    svc = ButterflyService(ohlcv_repo=mock_repo, cache=mock_cache)
    yield svc
    svc.shutdown()

def create_mock_df(n_periods=100, seed=42, constant=None):
    if constant is not None:
        data = [constant] * n_periods
    else:
        np.random.seed(seed)
        data = np.cumsum(np.random.randn(n_periods)) + 100
    return pd.DataFrame({
        'Close': data
    }, index=pd.date_range(start='2023-01-01', periods=n_periods))

@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_should_return_valid_response_model(service, mock_repo):
    """Verify basic success path returns a dict that matches ButterflyResponse."""
    df = create_mock_df(100)
    # Mock return for target and all macros (1 + 6)
    mock_repo.get.side_effect = [(df, "2024-05-16")] * 7

    result = await service.get_risk_map("AAPL")

    # Validate structure using the schema
    ButterflyResponse(**result)
    assert len(result["nodes"]) == 7 # Target + 6 macros
    assert result["nodes"][0]["id"] == "AAPL"
    assert result["nodes"][0]["ticker"] == "AAPL"
    assert "impact" in result["nodes"][0]

@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_should_sanitize_nan_correlations(service, mock_repo):
    """Verify nodes/edges with NaN correlation are filtered."""
    # Constant price leads to NaN correlation
    target_df = create_mock_df(100, seed=1)
    nan_macro_df = create_mock_df(100, constant=100.0)
    valid_macro_df = create_mock_df(100, seed=2)

    # side_effect order: target, SPY, USDIDR=X, CL=F, GC=F, BTC-USD, ^JKSE
    # Set SPY to NaN macro (returns constant price)
    side_effects = [
        (target_df, "2024"), # AAPL
        (nan_macro_df, "2024"), # SPY
        (valid_macro_df, "2024"), # USDIDR=X
        (valid_macro_df, "2024"), # CL=F
        (valid_macro_df, "2024"), # GC=F
        (valid_macro_df, "2024"), # BTC-USD
        (valid_macro_df, "2024"), # ^JKSE
    ]
    mock_repo.get.side_effect = side_effects

    result = await service.get_risk_map("AAPL")

    node_ids = [n["id"] for n in result["nodes"]]
    assert "AAPL" in node_ids
    assert "SPY" not in node_ids # Should be filtered due to NaN correlation

    # Verify no edges contain SPY
    for edge in result["edges"]:
        assert edge["source"] != "SPY"
        assert edge["target"] != "SPY"

@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_should_enforce_node_uniqueness(service, mock_repo):
    """Verify that duplicate node IDs are not present."""
    df = create_mock_df(100)
    # Mocking SPY to be same as target
    mock_repo.get.side_effect = [(df, "2024")] * 7

    # Intentionally add SPY to target if it was allowed, but here macros contains SPY
    # The service already handles this by checking seen_node_ids
    result = await service.get_risk_map("SPY") # Target is SPY

    node_ids = [n["id"] for n in result["nodes"]]
    assert node_ids.count("SPY") == 1

@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_should_prevent_dangling_edges(service, mock_repo):
    """Verify that edges pointing to nodes not in result set are discarded."""
    target_df = create_mock_df(100, seed=1)
    macro_df = create_mock_df(100, seed=2)

    # Only return data for target and ONE macro, rest None
    side_effects = [
        (target_df, "2024"), # AAPL
        (macro_df, "2024"), # SPY
        None, None, None, None, None # Other macros missing
    ]
    mock_repo.get.side_effect = side_effects

    result = await service.get_risk_map("AAPL")

    node_ids = set(n["id"] for n in result["nodes"])
    assert len(node_ids) == 2 # AAPL and SPY

    for edge in result["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids

@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_should_handle_insufficient_data(service, mock_repo):
    """Verify return of empty lists when less than 60 samples are available."""
    df_short = create_mock_df(50)
    mock_repo.get.side_effect = [(df_short, "2024")] * 7

    result = await service.get_risk_map("AAPL")

    assert result["status"] == "insufficient_data"
    assert result["nodes"] == []
    assert result["edges"] == []

@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_should_filter_self_edges(service, mock_repo):
    """Verify source != target in edges."""
    df = create_mock_df(100)
    mock_repo.get.side_effect = [(df, "2024")] * 7

    result = await service.get_risk_map("AAPL")

    for edge in result["edges"]:
        assert edge["source"] != edge["target"]
