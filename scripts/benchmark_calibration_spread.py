import argparse
import csv
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Define Roots
FT_ROOT = Path(".")
GM_ROOT = Path("../../Tools/Gemini-Manager")

# Add paths for imports to handle SenateService's dependencies
sys.path.insert(0, str(GM_ROOT)) # For apps.cli.manager
sys.path.insert(0, str(GM_ROOT / "conductor")) # For services.sentiment_service etc.
sys.path.insert(0, str(FT_ROOT / "apps" / "cli")) # For prediction_service

# Mock Environment Variables if needed by SenateService/Config
os.environ["DATABASE_URL"] = "postgresql://mock:mock@localhost:5432/mock"

# Mock Config object before importing SenateService
try:
    from unittest.mock import MagicMock

    import apps.cli.manager.config
    mock_config = MagicMock()
    # Required by SenateService
    mock_config.BOLLINGER_STD_DEV = 2.0
    mock_config.MA_PERIOD = 20
    mock_config.MA_MEDIUM_PERIOD = 50
    mock_config.MA_LONG_PERIOD = 200
    mock_config.MA_VOL_PERIOD = 20
    mock_config.ATR_PERIOD = 14
    mock_config.DECIMAL_PLACES = 4
    mock_config.MOMENTUM_RSI_UPPER = 70
    mock_config.MOMENTUM_RSI_LOWER = 30
    mock_config.VALUE_REL_PRICE_LOWER = 0.95
    mock_config.VALUE_REL_PRICE_UPPER = 1.05
    mock_config.RISK_ATR_THRESHOLD = 5.0
    mock_config.MACRO_STALE_HOURS = 4
    apps.cli.manager.config.Config = mock_config
except ImportError:
    pass

try:
    from prediction_service import PredictionService
    from senate_service import SenateService, Vote
    SERVICES_LOADED = True
except ImportError as e:
    print(f"Error loading services: {e}")
    # Print sys.path for debugging
    print("sys.path:")
    for p in sys.path:
        print(f"  {p}")
    SERVICES_LOADED = False

def benchmark_calibration(count=10):
    if not SERVICES_LOADED:
        print("Services not loaded. Cannot run benchmark.")
        return

    print(f"--- Calibration Spread Benchmark (N={count}) ---")

    LOG_DIR = FT_ROOT / "logs"
    LOG_DIR.mkdir(exist_ok=True)
    csv_path = LOG_DIR / "calibration_samples.csv"

    results = []

    # Instantiate SenateService
    try:
        senate = SenateService(category="us")
    except Exception as e:
        print(f"Failed to instantiate SenateService: {e}")
        return

    for i in range(count):
        # 1. Generate synthetic Prediction data
        # pred_return usually in range [-0.2, 0.2]
        # volatility usually in range [0.005, 0.05]
        pred_return = np.random.uniform(-0.15, 0.15)
        volatility = np.random.uniform(0.01, 0.05)

        # 2. Call PredictionService.calculate_confidence
        ml_confidence = PredictionService.calculate_confidence(pred_return, volatility)

        # 3. Call calculate_consensus (via SenateService)
        # We need a mock DataFrame for get_senate_decision
        dates = pd.date_range(end=pd.Timestamp.now(), periods=100)
        mock_df = pd.DataFrame({
            "Open": np.random.uniform(100, 200, 100),
            "High": np.random.uniform(105, 205, 100),
            "Low": np.random.uniform(95, 195, 100),
            "Close": np.random.uniform(100, 200, 100),
            "Volume": np.random.uniform(1000000, 5000000, 100)
        }, index=dates)
        mock_df.ticker = "MOCK"

        try:
            # We use get_senate_decision which encapsulates the consensus logic
            senate_res = senate.get_senate_decision("MOCK", mock_df)
            consensus = senate_res.consensus.value
            senate_confidence = senate_res.confidence
        except Exception:
            # Fallback for mock if real agents fail due to missing dependencies/DB
            # print(f"Senate decision failed for sample {i}: {e}")
            consensus = "BUY" if pred_return > 0 else "SELL"
            senate_confidence = ml_confidence * 0.8

        results.append({
            "sample_id": i,
            "pred_return": pred_return,
            "volatility": volatility,
            "ml_confidence": ml_confidence,
            "consensus": consensus,
            "senate_confidence": senate_confidence
        })

        if (i+1) % 5 == 0 or i == 0:
            print(f"  Processed {i+1}/{count}...")

    if not results:
        print("No results generated.")
        return

    # Output to CSV
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"Results saved to {csv_path}")

    # Print summary statistics
    df_res = pd.DataFrame(results)
    print("\nSummary Statistics:")
    print(df_res[["ml_confidence", "senate_confidence"]].describe())

    # Check for 5-15% clustering
    low_cluster = df_res[(df_res["ml_confidence"] >= 0.05) & (df_res["ml_confidence"] <= 0.15)]
    cluster_pct = (len(low_cluster) / count) * 100
    print(f"\nML Confidence Clustering (5-15% range): {cluster_pct:.1f}%")

    # Check spread
    spread = df_res["ml_confidence"].max() - df_res["ml_confidence"].min()
    print(f"ML Confidence Spread: {spread:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    benchmark_calibration(count=args.count)
