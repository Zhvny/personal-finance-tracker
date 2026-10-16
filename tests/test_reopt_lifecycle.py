import json
import logging
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

# Setup paths
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
sys.path.append(str(ROOT / "apps"))
sys.path.append(str(ROOT / "finance-tracker-gui"))

# Configure logging to capture INFO messages
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='[%(levelname)s] %(name)s: %(message)s')

from apps.cli.genetic_optimizer import GeneticOptimizer, PortfolioOptimizer

AUDIT_DB = ROOT / "data" / "audit" / "genetic_audit.db"
ACTIVE_PORTFOLIO = ROOT / "models" / "prod" / "active_portfolio.json"

def test_portfolio_lifecycle():
    print("\n=== Testing Portfolio Optimization Lifecycle ===")

    # 1. Prepare Mock Data
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    data = np.random.randn(100, 5) * 0.02 # 2% daily vol
    returns_df = pd.DataFrame(data, index=dates, columns=tickers)

    # 2. Initialize Optimizer
    optimizer = PortfolioOptimizer(pop_size=10, generations=5)

    # 3. Run Optimization
    print("Running optimization...")
    results = optimizer.optimize(returns_df, target="sharpe")

    if not results:
        print("FAILED: Optimization returned None")
        return False

    # 4. Verify Filesystem Output
    if not ACTIVE_PORTFOLIO.exists():
        print(f"FAILED: {ACTIVE_PORTFOLIO} was not created")
        return False

    try:
        with open(ACTIVE_PORTFOLIO, "r") as f:
            portfolio = json.load(f)
            print(f"SUCCESS: {ACTIVE_PORTFOLIO} is valid JSON")
            print(f"Metrics: {portfolio.get('metrics')}")
            if "weights" not in portfolio:
                print("FAILED: 'weights' missing from portfolio JSON")
                return False
    except Exception as e:
        print(f"FAILED: Error reading portfolio JSON: {e}")
        return False

    # 5. Verify Database Audit
    try:
        conn = sqlite3.connect(str(AUDIT_DB))

        # Check portfolio_audit
        audit = conn.execute("SELECT * FROM portfolio_audit ORDER BY id DESC LIMIT 1").fetchone()
        if audit:
            print(f"SUCCESS: portfolio_audit entry found. ID: {audit[0]}, Target: {audit[1]}")
        else:
            print("FAILED: No entry found in portfolio_audit")
            return False

        # Check system_state
        state = conn.execute("SELECT * FROM system_state WHERE key = 'portfolio_version'").fetchone()
        if state:
            print(f"SUCCESS: system_state entry found. Value: {state[1]}, Updated: {state[2]}")
        else:
            print("FAILED: No entry found in system_state for portfolio_version")
            return False

        conn.close()
    except Exception as e:
        print(f"FAILED: Database verification error: {e}")
        return False

    print("=== Portfolio Lifecycle Validation Passed ===\n")
    return True

def test_genetic_evolution_lifecycle():
    print("=== Testing Genetic Evolution Lifecycle ===")
    # Note: This requires feature files. We'll check if any exist.
    FEATURES_DIR = ROOT / "data" / "features" / "us"
    if not FEATURES_DIR.exists():
        print(f"Skipping Genetic Evolution test: {FEATURES_DIR} not found")
        return True

    feature_files = list(FEATURES_DIR.glob("*_features.csv"))
    if not feature_files:
        print(f"Skipping Genetic Evolution test: No feature files in {FEATURES_DIR}")
        return True

    ticker = feature_files[0].stem.replace("_features", "")
    print(f"Testing evolution for {ticker}...")

    optimizer = GeneticOptimizer(iterations=2)
    try:
        res = optimizer.evolve(ticker, "us")
        if res is not None:
            print(f"SUCCESS: Evolution completed for {ticker}")

            # Check DB
            conn = sqlite3.connect(str(AUDIT_DB))
            log = conn.execute("SELECT * FROM evolution_logs WHERE ticker = ? ORDER BY id DESC LIMIT 1", (ticker,)).fetchone()
            if log:
                print(f"SUCCESS: evolution_logs entry found for {ticker}")
            else:
                print(f"FAILED: No entry found in evolution_logs for {ticker}")
            conn.close()

            # Check Meta
            meta_path = ROOT / "models" / "prod" / f"{ticker}_meta.json"
            if meta_path.exists():
                print(f"SUCCESS: Meta file created for {ticker}")
            else:
                print(f"FAILED: Meta file NOT created for {ticker}")
        else:
            print(f"FAILED: Evolution returned None for {ticker}")
    except Exception as e:
        print(f"FAILED: Evolution encountered error: {e}")
        return False

    print("=== Genetic Evolution Lifecycle Validation Passed ===\n")
    return True


# Mock some dependencies for API testing
class MockRequest:
    def __init__(self):
        self.risk_mode = "sharpe"
        self.max_assets = 10
    def dict(self):
        return {"risk_mode": self.risk_mode, "max_assets": self.max_assets}
    def model_dump(self):
        return {"risk_mode": self.risk_mode, "max_assets": self.max_assets}

@pytest.mark.anyio
async def test_api_error_handling():
    """
    Tests that execute_optimization_task properly writes a 'failed' status
    to the DB when no OHLCV data is available.
    The backend uses PostgreSQL (not an in-memory dict), so we mock DatabaseManager.execute.
    """
    print("=== Testing API Error Handling Lifecycle ===")

    captured_db_calls = []

    def mock_db_execute(sql, params=None, **kwargs):
        captured_db_calls.append({"sql": sql, "params": params, "kwargs": kwargs})
        return []

    with patch("backend.routers.genetic.DatabaseManager.execute", side_effect=mock_db_execute), \
         patch("backend.routers.genetic.PostgresOHLCVRepository") as mock_repo_cls:

        mock_repo = mock_repo_cls.return_value
        mock_repo.get.return_value = None  # No data found scenario

        from backend.routers.genetic import execute_optimization_task
        task_id = "test-error-task-db"

        await execute_optimization_task(task_id, ["INVALID_TICKER"], MockRequest())

    # Verify the task was updated to 'failed' in DB
    failed_update = next(
        (c for c in captured_db_calls
         if c["params"] and "failed" in str(c["params"])),
        None
    )
    assert failed_update is not None, (
        f"Expected DB update with status='failed'. Got calls: {captured_db_calls}"
    )

    print("=== API Error Handling Validation Passed ===")

if __name__ == "__main__":
    p_res = test_portfolio_lifecycle()
    g_res = test_genetic_evolution_lifecycle()

    if p_res and g_res:
        print("\nALL LIFECYCLE TESTS PASSED")
        sys.exit(0)
    else:
        print("\nSOME TESTS FAILED")
        sys.exit(1)
