import asyncio
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pandas as pd

# Setup paths to import project modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
# Apps contains stock_analyzer
APPS_ROOT = PROJECT_ROOT / "apps"
sys.path.insert(0, str(APPS_ROOT))
# Backend is in packages/api/backend
BACKEND_ROOT = PROJECT_ROOT / "packages" / "api" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

# Mock DatabaseManager before importing StockRepository
sys.modules['packages.core.infrastructure.persistence.postgres_manager'] = MagicMock()

from repositories.stock_repository import StockRepository


class TestDXYIsolation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_config = MagicMock()
        # Mocking the actual classes to avoid real network calls
        with patch('repositories.stock_repository.DataFetcher') as mock_fetcher_cls, \
             patch('repositories.stock_repository.FREDFetcher') as mock_fred_cls:

            self.mock_fetcher = mock_fetcher_cls.return_value
            self.mock_fred_fetcher = mock_fred_cls.return_value

            self.repo = StockRepository(self.mock_config)
            self.repo._dxy_retry_delay = 0.01
            # Use default TTL (300) for testing isolation unless overridden

    async def test_non_blocking_macro_fetch(self):
        """Verify DXY fetch does not block return of base macro context."""
        print("\nTesting: Non-blocking macro fetch...")

        # Brent returns immediately
        # DXY takes 1 second (simulated in thread pool)
        def side_effect(ticker, period):
            if ticker == "DX-Y.NYB":
                time.sleep(1)
                return pd.DataFrame({'Close': [100]})
            return pd.DataFrame({'Close': [50]})

        self.mock_fetcher.fetch.side_effect = side_effect
        self.mock_fred_fetcher.get_macro_context.return_value = {"status": "ok", "regime": "RECOVERY"}

        loop = asyncio.get_event_loop()
        start_time = loop.time()

        # This should return Brent context quickly, even if DXY is still fetching
        macro_data = await self.repo.get_macro_context()
        end_time = loop.time()

        elapsed = end_time - start_time
        print(f"Macro context returned in {elapsed:.4f}s")

        # Verify it returned quickly (well under the 1s DXY delay)
        self.assertLess(elapsed, 0.5, "Macro fetch blocked by background DXY sync")
        self.assertEqual(macro_data["regime"], "RECOVERY")

        # Give a small window for background task to start
        await asyncio.sleep(0.05)

        # Verify DXY sync was started in background
        status = await self.repo.get_dxy_status()
        # It might be syncing or already ready if the thread finished super fast (unlikely with sleep(1))
        self.assertTrue(status["is_syncing"] or status["is_ready"], "DXY sync should be active or complete")

        # Wait for DXY to finish to avoid resource leaks in tests
        for _ in range(20):
            if (await self.repo.get_dxy_status())["is_ready"]:
                break
            await asyncio.sleep(0.1)

        print("SUCCESS: Macro context non-blocking")

    async def test_caching_ttl_compliance(self):
        """Verify macro context respects the 300s TTL."""
        print("\nTesting: TTL compliance (300s)...")

        # We need to mock time.time() inside stock_repository
        with patch('repositories.stock_repository.time.time') as mock_time:
            # t=1000: Initial fetch
            mock_time.return_value = 1000.0
            self.mock_fetcher.fetch.return_value = pd.DataFrame({'Close': [100]})
            self.mock_fred_fetcher.get_macro_context.return_value = {"status": "ok", "val": 1}

            await self.repo.get_macro_context()
            # Brent fetch + FRED fetch
            brent_calls = sum(1 for call in self.mock_fetcher.fetch.call_args_list if call[0][0] == "CL=F")
            self.assertEqual(brent_calls, 1)
            self.mock_fetcher.fetch.assert_called_with("CL=F", ANY)

            # t=1299: Within TTL (300s)
            mock_time.return_value = 1299.0
            data_2 = await self.repo.get_macro_context()
            brent_calls = sum(1 for call in self.mock_fetcher.fetch.call_args_list if call[0][0] == "CL=F")
            self.assertEqual(brent_calls, 1, "Should have used cache at t=1299")
            self.assertEqual(data_2["val"], 1)

            # t=1301: Expired TTL
            mock_time.return_value = 1301.0
            self.mock_fred_fetcher.get_macro_context.return_value = {"status": "ok", "val": 2}
            data_3 = await self.repo.get_macro_context()
            brent_calls = sum(1 for call in self.mock_fetcher.fetch.call_args_list if call[0][0] == "CL=F")
            self.assertEqual(brent_calls, 2, "Should have refreshed at t=1301")
            self.assertEqual(data_3["val"], 2)

        print("SUCCESS: TTL compliance verified")

    async def test_dxy_fetch_isolation(self):
        """Verify DXY fetch failure does not affect base macro context."""
        print("\nTesting: DXY fetch isolation...")

        # Success for Brent, Failure for DXY
        def side_effect(ticker, period):
            if ticker == "DX-Y.NYB":
                raise Exception("DXY Network Timeout")
            return pd.DataFrame({'Close': [50]})

        self.mock_fetcher.fetch.side_effect = side_effect
        self.mock_fred_fetcher.get_macro_context.return_value = {"status": "ok", "regime": "EXPANSION"}

        # Should still return macro context successfully
        macro_data = await self.repo.get_macro_context()
        self.assertEqual(macro_data["regime"], "EXPANSION")

        # Wait for background task to fail
        await asyncio.sleep(0.1)

        status = await self.repo.get_dxy_status()
        self.assertFalse(status["is_ready"])
        self.assertFalse(status["is_syncing"])

        # Check that we can still get macro context again
        self.repo._macro_cache["timestamp"] = 0 # Force expire
        macro_data_2 = await self.repo.get_macro_context()
        self.assertEqual(macro_data_2["regime"], "EXPANSION")

        print("SUCCESS: DXY failure isolated")

    async def test_background_sync_isolation_benchmarks(self):
        """Verify DXY background sync adds < 50ms overhead (REQ-7)."""
        print("\nTesting: Background sync isolation benchmarks (REQ-7)...")

        # Simulate heavy load for DXY fetch
        def slow_dxy_side_effect(ticker, period):
            if ticker == "DX-Y.NYB":
                # Simulated long network delay for DXY
                time.sleep(1.0)
                return pd.DataFrame({'Close': [104.5]})
            # Fast return for Brent
            return pd.DataFrame({'Close': [85.0]})

        self.mock_fetcher.fetch.side_effect = slow_dxy_side_effect
        self.mock_fred_fetcher.get_macro_context.return_value = {
            "status": "ok",
            "regime": "EXPANSION",
            "brent": 85.0
        }

        # Warm up: The first call starts the background sync
        # We measure this call to ensure it returns fast despite DXY sync starting
        loop = asyncio.get_event_loop()

        # Run 5 iterations to get an average/consistent measurement
        latencies = []
        for i in range(5):
            # Clear internal state to force a new sync task
            # Using exact keys from stock_repository.py to ensure complete reset
            self.repo._macro_cache = {
                "data": None,
                "timestamp": 0,
                "dxy": None,
                "is_syncing_dxy": False
            }

            start_time = loop.time()
            macro_data = await self.repo.get_macro_context()
            end_time = loop.time()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

            # Verify data integrity
            self.assertEqual(macro_data["regime"], "EXPANSION")
            self.assertEqual(macro_data["brent"], 85.0)

            # Give a very tiny window for the task to start and update status
            await asyncio.sleep(0.01)

            # Ensure background sync is actually running
            status = await self.repo.get_dxy_status()
            self.assertTrue(status["is_syncing"], f"Iteration {i}: Background sync should be active")

            # Give it a moment before next iteration
            await asyncio.sleep(0.05)

        avg_latency = sum(latencies) / len(latencies)
        print(f"Average macro fetch latency with background DXY sync: {avg_latency:.2f}ms")
        print(f"Individual latencies: {[f'{l:.2f}ms' for l in latencies]}")

        # REQ-7: Benchmark threshold < 50ms
        self.assertLess(avg_latency, 50, f"Average latency {avg_latency:.2f}ms exceeds 50ms limit")

        # Cleanup: Wait for the last background task
        for _ in range(20):
            if (await self.repo.get_dxy_status())["is_ready"]:
                break
            await asyncio.sleep(0.1)

        print("SUCCESS: Performance benchmark compliant with REQ-7")

if __name__ == "__main__":
    unittest.main()
