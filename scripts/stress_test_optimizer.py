import asyncio
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

# Setup paths
PROJECT_ROOT = Path(".")
MANAGER_ROOT = Path("../../Tools/Gemini-Manager")

sys.path.append(str(PROJECT_ROOT / "apps"))
sys.path.append(str(MANAGER_ROOT / "apps" / "cli"))

from genetic_optimizer import PortfolioOptimizer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_ill_conditioned_data(n_assets, n_days=252):
    """Generates returns with high correlation to test numerical stability."""
    tickers = [f"TKR_{i:03d}" for i in range(n_assets)]
    # Base market factor
    market = np.random.normal(0.0005, 0.01, n_days)

    data = np.zeros((n_days, n_assets))
    for i in range(n_assets):
        # Every asset is 99% correlated with the market factor + 1% noise
        noise = np.random.normal(0, 0.001, n_days)
        data[:, i] = 0.99 * market + 0.01 * noise

    return pd.DataFrame(data, columns=tickers)

def generate_extreme_data(n_assets, n_days=252):
    """Generates returns with extreme values."""
    tickers = [f"TKR_{i:03d}" for i in range(n_assets)]
    data = np.random.normal(0, 0.01, (n_days, n_assets))
    # Inject extreme values
    data[10, 0] = 10.0 # 1000% return in one day
    data[20, 1] = -0.9 # 90% drop
    return pd.DataFrame(data, columns=tickers)

async def test_timeout_handling():
    logger.info("Testing Timeout Handling...")
    optimizer = PortfolioOptimizer(pop_size=500, generations=500) # Large job
    returns_df = generate_ill_conditioned_data(100)

    start_time = time.time()
    try:
        # We expect this to be slow, so we set a tight timeout
        await asyncio.wait_for(optimizer.optimize_async(returns_df), timeout=0.1)
        logger.error("  FAIL: Optimizer should have timed out but didn't.")
        return False
    except asyncio.TimeoutError:
        duration = time.time() - start_time
        logger.info(f"  PASS: Optimizer timed out correctly after {duration:.4f}s")
        return True
    except Exception as e:
        logger.error(f"  FAIL: Unexpected error during timeout test: {e}")
        return False

def test_numerical_stability():
    logger.info("Testing Numerical Stability (Ill-conditioned Matrix)...")
    optimizer = PortfolioOptimizer(pop_size=50, generations=20)
    returns_df = generate_ill_conditioned_data(50)

    try:
        result = optimizer.optimize(returns_df)
        metrics = result["final_metrics"]
        logger.info(f"  Final Metrics: Ret={metrics[0]:.4f}, Vol={metrics[1]:.4f}, Sharpe={metrics[2]:.4f}")

        # Check if metrics are finite
        if all(np.isfinite(metrics)):
            logger.info("  PASS: Optimizer handled ill-conditioned matrix without NaN/Inf.")
            return True
        else:
            logger.error(f"  FAIL: Non-finite metrics detected: {metrics}")
            return False
    except Exception as e:
        logger.error(f"  FAIL: Optimizer crashed on ill-conditioned matrix: {e}")
        return False

def test_extreme_values():
    logger.info("Testing Numerical Stability (Extreme Values)...")
    optimizer = PortfolioOptimizer(pop_size=50, generations=20)
    returns_df = generate_extreme_data(50)

    try:
        result = optimizer.optimize(returns_df)
        metrics = result["final_metrics"]
        logger.info(f"  Final Metrics: Ret={metrics[0]:.4f}, Vol={metrics[1]:.4f}, Sharpe={metrics[2]:.4f}")

        if all(np.isfinite(metrics)):
            logger.info("  PASS: Optimizer handled extreme values correctly.")
            return True
        else:
            logger.error(f"  FAIL: Non-finite metrics with extreme values: {metrics}")
            return False
    except Exception as e:
        logger.error(f"  FAIL: Optimizer crashed on extreme values: {e}")
        return False

def test_memory_safety():
    logger.info("Testing Memory Safety...")
    optimizer = PortfolioOptimizer(pop_size=100, generations=50)
    returns_df = generate_ill_conditioned_data(250)

    process = psutil.Process(os.getpid())
    mem_start = process.memory_info().rss / (1024 * 1024)

    # Run multiple times to check for leak
    for i in range(5):
        optimizer.optimize(returns_df)

    mem_end = process.memory_info().rss / (1024 * 1024)
    leak = mem_end - mem_start
    logger.info(f"  Memory Start: {mem_start:.2f}MB, End: {mem_end:.2f}MB, Delta: {leak:.2f}MB")

    # We allow some growth due to python's GC, but it shouldn't be massive
    if leak < 100:
        logger.info("  PASS: No significant memory leak detected.")
        return True
    else:
        logger.error(f"  FAIL: Significant memory growth detected: {leak:.2f}MB")
        return False

def test_convergence_reliability():
    logger.info("Testing Convergence Reliability...")
    optimizer = PortfolioOptimizer(pop_size=100, generations=100)
    returns_df = generate_ill_conditioned_data(50)

    results = []
    for i in range(3):
        res = optimizer.optimize(returns_df)
        results.append(res["diagnostics"]["convergence_delta"])

    avg_delta = np.mean(results)
    logger.info(f"  Average Convergence Delta: {avg_delta:.6f}")

    if avg_delta < 0.1: # Threshold for reasonable improvement
        logger.info("  PASS: Optimizer shows reliable convergence.")
        return True
    else:
        logger.error(f"  FAIL: Poor convergence detected. Delta: {avg_delta:.6f}")
        return False

async def main():
    results = {
        "timeout": await test_timeout_handling(),
        "numerical_stability": test_numerical_stability(),
        "extreme_values": test_extreme_values(),
        "memory_safety": test_memory_safety(),
        "convergence": test_convergence_reliability()
    }

    print("\n" + "="*30)
    print("STRESS TEST SUMMARY")
    print("="*30)
    for test, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"{test.replace('_', ' ').title():<20}: {status}")
    print("="*30)

    if not all(results.values()):
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
