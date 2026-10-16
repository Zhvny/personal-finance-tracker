from unittest.mock import MagicMock

import pandas as pd
import pytest

from packages.core.application.butterfly_service import ButterflyService


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_get_risk_map_returns_graph():
    """
    Test that ButterflyService returns a graph structure {nodes, edges}.
    """
    mock_repo = MagicMock()

    # Create dummy DataFrames
    df = pd.DataFrame({
        'Close': [100 + i for i in range(100)]
    }, index=pd.date_range(start='2023-01-01', periods=100))

    # Macro data slightly different
    macro_df = pd.DataFrame({
        'Close': [105 + (i * 1.1) for i in range(100)]
    }, index=pd.date_range(start='2023-01-01', periods=100))

    service = ButterflyService(ohlcv_repo=mock_repo)

    # Mock enough side effects for target and ALL macros (1 target + 6 macros)
    side_effects = [(df, "2024-05-16")] + [(macro_df, "2024-05-16")] * 6
    mock_repo.get.side_effect = side_effects

    result = await service.get_risk_map("AAPL")

    assert isinstance(result, dict)
    assert "nodes" in result
    assert "edges" in result
    assert len(result["nodes"]) > 0
    # First node should be the target
    assert result["nodes"][0]["id"] == "AAPL"
    # Check if macros are present
    macro_tickers = [n["id"] for n in result["nodes"][1:]]
    assert any(ticker in service.macros for ticker in macro_tickers)

@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.anyio
async def test_generate_mock_risk_map():
    """
    Test that generate_mock_risk_map returns a synthetic graph.
    """
    service = ButterflyService(ohlcv_repo=MagicMock())
    result = await service.generate_mock_risk_map(node_count=10, edge_density=0.5)

    assert isinstance(result, dict)
    assert len(result["nodes"]) == 10
    assert "metadata" in result
    assert result["metadata"]["is_mock"] is True
    assert "generation_time_ms" in result["metadata"]
    assert result["metadata"]["node_count"] == 10
    assert "edges" in result
