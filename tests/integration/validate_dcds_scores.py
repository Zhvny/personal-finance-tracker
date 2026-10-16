import logging
import os
import sys
from pathlib import Path

import pandas as pd

# Add apps and root directory to sys.path
project_root = str(Path(__file__).resolve().parent.parent.parent)
apps_path = os.path.join(project_root, "apps")
if project_root not in sys.path:
    sys.path.append(project_root)
if apps_path not in sys.path:
    sys.path.append(apps_path)

from unittest.mock import MagicMock

from stock_analyzer.adapters.cache import DataCache
from stock_analyzer.adapters.fetcher import DataFetcher
from stock_analyzer.adapters.fred_fetcher import FREDFetcher
from stock_analyzer.adapters.indicators import IndicatorEngine
from stock_analyzer.domain.scoring import ScoringEngine
from stock_analyzer.infrastructure.macro_repository import MacroRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def manual_dcds(comm_series, dxy_series, window=20):
    # Standardize to naive
    comm = comm_series.copy()
    if comm.index.tz is not None:
        comm.index = comm.index.tz_localize(None)
    dxy = dxy_series.copy()
    if dxy.index.tz is not None:
        dxy.index = dxy.index.tz_localize(None)

    # Align
    comm = comm.reindex(dxy.index, method="ffill")

    # Z-Score
    comm_mean = comm.rolling(window).mean()
    comm_std = comm.rolling(window).std().fillna(0)
    comm_z = (comm - comm_mean) / (comm_std + 1e-9)

    dxy_mean = dxy.rolling(window).mean()
    dxy_std = dxy.rolling(window).std().fillna(0)
    dxy_z = (dxy - dxy_mean) / (dxy_std + 1e-9)

    return comm_z + dxy_z


def validate_assets():
    # Setup
    cache = DataCache(db_path="test_validation.db")
    fetcher = DataFetcher(cache=cache)
    indicator_engine = IndicatorEngine()

    # Mock FRED for MacroRepository
    config = MagicMock()
    fred = FREDFetcher(config)
    macro_repo = MacroRepository(fred, fetcher)

    assets = ["AAPL", "BTC-USD", "GC=F"]  # GOLD is GC=F on Yahoo
    dxy_ticker = "DX-Y.NYB"

    logger.info("Fetching data for validation...")
    dxy_df = fetcher.fetch(dxy_ticker)
    if dxy_df.empty:
        logger.error("Could not fetch DXY data.")
        return

    for asset in assets:
        logger.info(f"Validating {asset}...")
        asset_df = fetcher.fetch(asset)
        if asset_df.empty:
            logger.warning(f"Could not fetch {asset} data. Skipping.")
            continue

        # Compute using engine
        processed_df = indicator_engine.compute_dcds(asset_df.copy(), dxy_df)
        engine_dcds = processed_df["dcds"]

        # Manual compute
        manual_scores = manual_dcds(asset_df["Close"], dxy_df["Close"])

        # Align engine_dcds with manual_scores for comparison (engine might have different index if reindexed)
        # IndicatorEngine.compute_dcds returns the original asset_df with a 'dcds' column.
        # But wait, looking at compute_dcds code:
        # comm = comm.reindex(dxy.index, method='ffill')
        # df['dcds'] = comm_z + dxy_z
        # Since df is the asset_df, but comm_z + dxy_z is indexed by dxy.index,
        # this assignment might be misaligned if df and dxy have different indices!

        # Let's check alignment in my validation script
        comparison = pd.DataFrame({"engine": engine_dcds, "manual": manual_scores}).dropna()

        if comparison.empty:
            logger.error(f"No overlapping data for {asset} and DXY.")
            continue

        # Check variance
        diff = (comparison["engine"] - comparison["manual"]).abs()
        max_diff = diff.max()
        avg_diff = diff.mean()

        logger.info(f"{asset} Results -> Max Diff: {max_diff:.8f}, Avg Diff: {avg_diff:.8f}")

        if max_diff > 1e-5:
            logger.error(f"High variance detected for {asset}!")
            # Print last few rows to debug
            print(comparison.tail())
        else:
            logger.info(f"{asset} validation PASSED (< 5% variance, actually nearly zero).")

    # NEW: Verify CSS Bonus
    logger.info("Verifying CSS bonus from DCDS...")
    mock_context = {"lpi": 0.5, "icm": 0.0, "errf_mult": 1.0, "csi": 70.0}
    tech_score = 7.0

    # No bonus case
    css_no_bonus, _ = ScoringEngine.calculate_css(tech_score, mock_context, is_commodity=True, dcds=0.0)
    # High DCDS bonus case
    css_with_bonus, _ = ScoringEngine.calculate_css(tech_score, mock_context, is_commodity=True, dcds=2.0)

    logger.info(f"CSS No Bonus: {css_no_bonus}, CSS With Bonus: {css_with_bonus}")
    assert css_with_bonus > css_no_bonus, "CSS should increase with high DCDS for commodities"
    assert (
        css_with_bonus == css_no_bonus + 5.0
    ), f"Expected 5.0 CSS points bonus (0.5 macro bonus * 10), got {css_with_bonus - css_no_bonus}"
    logger.info("CSS bonus validation PASSED.")


if __name__ == "__main__":
    validate_assets()
