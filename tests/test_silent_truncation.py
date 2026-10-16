import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Setup paths to import from Gemini-Manager/apps/cli
MANAGER_ROOT = Path("../../Tools/Gemini-Manager")
sys.path.append(str(MANAGER_ROOT / "apps" / "cli"))

from genetic_optimizer import PortfolioOptimizer


def generate_mock_returns(n_assets, n_days=100):
    tickers = [f"TKR_{i:03d}" for i in range(n_assets)]
    data = np.random.normal(0.0005, 0.01, (n_days, n_assets))
    return pd.DataFrame(data, columns=tickers)

def test_silent_truncation_warning(caplog):
    """Verify that the optimizer logs a critical warning when assets <= threshold."""
    # We'll use a small threshold to trigger the warning
    # Note: Config.OPTIMIZER_TRUNCATION_THRESHOLD defaults to 3 if not set in config.yaml
    # But in the code it was if n_assets <= threshold.

    # We force the threshold to 10 for this test if possible,
    # but we can't easily mock Config properties that are already loaded.
    # So we'll use a very small number of assets (2).

    optimizer = PortfolioOptimizer(pop_size=10, generations=5)
    returns_df = generate_mock_returns(n_assets=2)

    with caplog.at_level(logging.CRITICAL):
        result = optimizer.optimize(returns_df)

    assert "SILENT TRUNCATION" in caplog.text
    assert "running on only 2 assets" in caplog.text
    assert result["diagnostics"]["truncation_warning"] is True

def test_no_silent_truncation_on_large_universe(caplog):
    """Verify no warning when universe is sufficiently large."""
    optimizer = PortfolioOptimizer(pop_size=10, generations=5)
    returns_df = generate_mock_returns(n_assets=20)

    with caplog.at_level(logging.CRITICAL):
        result = optimizer.optimize(returns_df)

    assert "SILENT TRUNCATION" not in caplog.text
    assert result["diagnostics"]["truncation_warning"] is False
