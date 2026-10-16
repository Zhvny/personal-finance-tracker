"""
tests/mock_data_provider.py

Provides synthetic stock-return DataFrames and failure-injection utilities
for testing the GeneticPortfolioOptimizer under adversarial data conditions.
"""
from typing import Any, Dict

import numpy as np
import pandas as pd


def generate_mock_returns(
    n_assets: int = 10,
    n_periods: int = 252,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate a DataFrame of synthetic daily log-returns.

    Parameters
    ----------
    n_assets : int
        Number of tickers/assets to generate.
    n_periods : int
        Number of trading-day periods (rows).
    seed : int
        NumPy random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        Shape (n_periods, n_assets) with columns like ``TKR_000``, ``TKR_001``, …
    """
    rng = np.random.default_rng(seed)
    tickers = [f"TKR_{i:03d}" for i in range(n_assets)]
    data = rng.normal(loc=0.0005, scale=0.02, size=(n_periods, n_assets))
    dates = pd.bdate_range(end="2024-12-31", periods=n_periods)
    return pd.DataFrame(data, index=dates, columns=tickers)


def inject_failure_modes(
    df: pd.DataFrame,
    failure_map: Dict[str, Any],
) -> pd.DataFrame:
    """
    Corrupt specific columns of a returns DataFrame to simulate bad market data.

    Parameters
    ----------
    df : pd.DataFrame
        Clean returns DataFrame produced by :func:`generate_mock_returns`.
    failure_map : dict
        A dict describing which failure modes to apply and to which tickers.
        Supported keys:

        * ``"all_nan"``      – list[str] : replace entire column with NaN
        * ``"partial_nan"``  – dict[str, int] : replace *n* leading rows with NaN
        * ``"inf"``          – list[str] : replace entire column with +np.inf

    Returns
    -------
    pd.DataFrame
        A copy of *df* with the requested corruptions applied.

    Examples
    --------
    >>> df = generate_mock_returns(n_assets=5)
    >>> failure_map = {
    ...     "all_nan":     ["TKR_000"],
    ...     "partial_nan": {"TKR_002": 10},
    ...     "inf":         ["TKR_004"],
    ... }
    >>> bad_df = inject_failure_modes(df, failure_map)
    """
    result = df.copy()

    # --- all_nan: replace entire column -----------------------------------
    for ticker in failure_map.get("all_nan", []):
        if ticker in result.columns:
            result[ticker] = np.nan

    # --- partial_nan: replace first `n` rows with NaN --------------------
    partial = failure_map.get("partial_nan", {})
    for ticker, n_rows in partial.items():
        if ticker in result.columns:
            result.iloc[:n_rows, result.columns.get_loc(ticker)] = np.nan

    # --- inf: replace entire column with positive infinity ---------------
    for ticker in failure_map.get("inf", []):
        if ticker in result.columns:
            result[ticker] = np.inf

    return result
