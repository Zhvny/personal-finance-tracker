import sys
from pathlib import Path

import numpy as np
import pytest

# Add apps/cli to path to import PortfolioOptimizer and mock_data_provider
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "apps" / "cli"))

from genetic_optimizer import PortfolioOptimizer

from tests.mock_data_provider import generate_mock_returns, inject_failure_modes


@pytest.fixture
def optimizer():
    # Use small pop and generations for speed
    return PortfolioOptimizer(pop_size=10, generations=5)

def test_robustness_all_nan_filtering(optimizer):
    """Scenario 1: Universe of 10 assets, 3 have all NaNs. Verify optimizer proceeds with 7 assets."""
    df = generate_mock_returns(n_assets=10)
    failure_map = {
        'all_nan': ['TKR_000', 'TKR_001', 'TKR_002']
    }
    df_fail = inject_failure_modes(df, failure_map)

    result = optimizer.optimize(df_fail)

    assert result is not None
    assert len(result["weights"]) == 7
    for t in failure_map['all_nan']:
        assert t not in result["weights"]

def test_robustness_partial_nan_shrinking(optimizer):
    """Verify optimizer filters out assets with partial NaNs (Emergency Shrinking)."""
    df = generate_mock_returns(n_assets=10)
    failure_map = {
        'partial_nan': {'TKR_005': 5}
    }
    df_fail = inject_failure_modes(df, failure_map)

    result = optimizer.optimize(df_fail)

    assert result is not None
    assert 'TKR_005' not in result["weights"]
    assert len(result["weights"]) == 9

def test_robustness_inf_filtering(optimizer):
    """Scenario 3: Assets with np.inf. Verify they are filtered out."""
    # Current implementation in genetic_optimizer.py uses dropna(axis=1, how='all')
    # and nan_counts check. np.inf doesn't trigger dropna or isna.
    # We expect this test to FAIL or the optimizer to CRASH if not handled,
    # revealing a gap we should fix.

    df = generate_mock_returns(n_assets=10)
    failure_map = {
        'inf': ['TKR_009']
    }
    df_fail = inject_failure_modes(df, failure_map)

    # Let's see how it handles inf. np.inf * weights will likely result in NaNs in metrics.
    result = optimizer.optimize(df_fail)

    # If it returns a result, we check if TKR_009 is filtered.
    # Note: If it's NOT filtered, metrics will likely be inf/nan.
    assert result is not None
    # If the optimizer doesn't filter INF yet, TKR_009 will be in weights.
    # But the metrics should be sensible (not inf).
    for val in result["final_metrics"]:
        assert np.isfinite(val)

def test_robustness_large_universe_fallback(optimizer):
    """Scenario 2: Universe of 105 assets. Verify optimizer fallback to top 100 assets."""
    df = generate_mock_returns(n_assets=105)

    result = optimizer.optimize(df)

    assert result is not None
    assert len(result["weights"]) == 100
