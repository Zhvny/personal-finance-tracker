import concurrent.futures
import json
import sys
import time
from pathlib import Path

# Ensure project root is in path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from apps.cli.investment_tracker.services.simulation_engine import SimulationEngine


def run_sequential(n_sims=50, iterations=10000):
    start = time.time()
    for _ in range(n_sims):
        SimulationEngine.run_monte_carlo(100.0, 0.02, iterations=iterations)
    return time.time() - start

def run_parallel(n_sims=50, iterations=10000):
    start = time.time()
    # Using 4 workers for benchmark
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(SimulationEngine.run_monte_carlo, 100.0, 0.02, iterations=iterations) for _ in range(n_sims)]
        results = [f.result() for f in futures]
    return time.time() - start

def main():
    n_sims = 40
    iters = 50000
    print(f"Benchmarking Monte Carlo Latency (n_sims={n_sims}, iters={iters})...")

    # Warmup
    SimulationEngine.run_monte_carlo(100.0, 0.02, iterations=1000)

    t_seq = run_sequential(n_sims, iterations=iters)
    print(f"Sequential: {t_seq:.4f}s")

    t_par = run_parallel(n_sims, iterations=iters)
    print(f"Parallel: {t_par:.4f}s")

    speedup = t_seq / t_par
    print(f"Speedup: {speedup:.2f}x")

    report = {
        "n_sims": n_sims,
        "iterations_per_sim": iters,
        "sequential_seconds": t_seq,
        "parallel_seconds": t_par,
        "speedup": speedup
    }

    Path("logs").mkdir(exist_ok=True)
    with open("logs/monte_carlo_benchmark_report.json", "w") as f:
        json.dump(report, f, indent=4)
    print("Report saved to logs/monte_carlo_benchmark_report.json")

if __name__ == '__main__':
    main()
