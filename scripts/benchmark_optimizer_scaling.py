import json
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

# Add paths to sys.path to resolve imports correctly
# 1. Finance Tracker apps (for stock_analyzer)
sys.path.append(str(PROJECT_ROOT / "apps"))
# 2. Gemini Manager apps/cli (for genetic_optimizer and its local manager/ imports)
sys.path.append(str(MANAGER_ROOT / "apps" / "cli"))

from genetic_optimizer import PortfolioOptimizer


def generate_mock_returns(n_assets, n_days=252):
    """Generate synthetic returns for benchmarking."""
    tickers = [f"TICKER_{i}" for i in range(n_assets)]
    # Random walk returns
    data = np.random.normal(0.0005, 0.01, (n_days, n_assets))
    return pd.DataFrame(data, columns=tickers)

def measure_resource_usage(func, *args, **kwargs):
    """Measures runtime and peak memory for a function call."""
    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss

    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()

    # This is an approximation of peak memory by checking after execution
    mem_after = process.memory_info().rss
    peak_mem_mb = (mem_after - mem_before) / (1024 * 1024)

    return result, {
        "runtime_sec": end_time - start_time,
        "memory_delta_mb": peak_mem_mb,
        "peak_rss_mb": mem_after / (1024 * 1024)
    }

def run_benchmarks():
    universe_sizes = [50, 100, 250, 526]
    results = {}

    # Configure optimizer for benchmarking (fast runs)
    # Use realistic population size for benchmarking scaling behavior
    optimizer = PortfolioOptimizer(
        pop_size=50,
        generations=20,
        mutation_rate=0.1
    )

    print("Starting Optimizer Scaling Benchmark...")
    print("Settings: pop_size=50, generations=20")
    print("-" * 50)

    for size in universe_sizes:
        print(f"Benchmarking universe size: {size}...")

        # Generate data
        returns_df = generate_mock_returns(size)

        # Run optimization with measurements
        opt_result, metrics = measure_resource_usage(
            optimizer.optimize,
            returns_df,
            target="sharpe"
        )

        # Extract iteration history length as a proxy for convergence/full run
        actual_gens = len(opt_result.get("fitness_history", []))

        results[str(size)] = {
            "universe_size": size,
            "runtime_sec": metrics["runtime_sec"],
            "memory_delta_mb": metrics["memory_delta_mb"],
            "peak_rss_mb": metrics["peak_rss_mb"],
            "actual_generations": actual_gens,
            "selected_assets": len([w for w in opt_result["weights"].values() if w > 0])
        }

        print(f"  Done. Runtime: {metrics['runtime_sec']:.2f}s, Peak RSS: {metrics['peak_rss_mb']:.2f}MB")

    # Save results
    LOG_DIR = MANAGER_ROOT / "logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    output_path = LOG_DIR / "benchmark_results.json"

    with open(output_path, "w") as f:
        json.dump(results, f, indent=4)

    print("-" * 50)
    print(f"Benchmark complete. Results saved to {output_path}")

if __name__ == "__main__":
    run_benchmarks()
