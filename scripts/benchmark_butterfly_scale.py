import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

# Force absolute imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.application.butterfly_service import ButterflyService
from packages.core.infrastructure.cache.butterfly_cache import ButterflyCache


class MockRepository:
    def get(self, ticker, period):
        dates = pd.date_range(end=pd.Timestamp("2024-05-16"), periods=252, freq='D')
        # Use a stable seed for consistent mock data
        seed = sum(ord(c) for c in ticker) % (2**32)
        np.random.seed(seed)
        df = pd.DataFrame({'Close': np.random.randn(252).cumsum() + 100}, index=dates)
        return df, pd.Timestamp("2024-05-16")

async def benchmark_scale(node_count, stress_real_logic=False):
    repo = MockRepository()

    # Use a real temp file to satisfy ButterflyCache's mkdir/sqlite requirements
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        cache = ButterflyCache(db_path=db_path)
        service = ButterflyService(ohlcv_repo=repo, cache=cache)

        if stress_real_logic:
            # Monkeypatch macros to reach target node count
            # We want node_count total, so target + (node_count - 1) macros
            service.macros = {f"MOCK_{i}": f"Mock Desc {i}" for i in range(node_count - 1)}

        process = psutil.Process(os.getpid())
        # Clear some memory before starting
        import gc
        gc.collect()

        mem_before = process.memory_info().rss / (1024 * 1024)

        start_time = time.perf_counter()

        # Calculate risk map with requested scale
        result = await service.get_risk_map("TARGET", max_nodes=node_count, max_edges=node_count * 10)

        duration = (time.perf_counter() - start_time) * 1000
        mem_after = process.memory_info().rss / (1024 * 1024)

        service.shutdown()

        return {
            "nodes": len(result.get("nodes", [])),
            "edges": len(result.get("edges", [])),
            "time_ms": duration,
            "rss_mb": mem_after,
            "delta_mb": mem_after - mem_before
        }
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except:
                pass

async def main():
    print("Butterfly Scale Benchmark (Real Logic - Correlation Matrix Calculation)")
    print(f"{'Target Nodes':<12} | {'Nodes':<10} | {'Edges':<10} | {'Time (ms)':<15} | {'RSS (MB)':<15}")
    print("-" * 75)

    for scale in [10, 100, 500]:
        res = await benchmark_scale(scale, stress_real_logic=True)
        print(f"{scale:<12} | {res['nodes']:<10} | {res['edges']:<10} | {res['time_ms']:<15.2f} | {res['rss_mb']:<15.2f}")

if __name__ == "__main__":
    asyncio.run(main())
