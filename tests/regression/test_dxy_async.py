import asyncio
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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


class TestDXYAsync(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_config = MagicMock()
        # Mocking the actual classes to avoid real network calls
        with patch('repositories.stock_repository.DataFetcher') as mock_fetcher_cls, \
             patch('repositories.stock_repository.FREDFetcher') as mock_fred_cls:

            self.mock_fetcher = mock_fetcher_cls.return_value
            self.mock_fred_fetcher = mock_fred_cls.return_value

            self.repo = StockRepository(self.mock_config)
            # Ensure TTL is short for testing or we'll manually expire it
            self.repo._cache_ttl = 1
            self.repo._dxy_retry_delay = 0.01

    async def test_dxy_load_after_restart(self):
        """Regression: DXY load after app restart (empty cache)"""
        print("\nTesting: DXY load after app restart...")

        # Setup mocks
        dummy_df = pd.DataFrame({'Close': [100, 101]}, index=pd.date_range('2026-01-01', periods=2))
        self.mock_fetcher.fetch.return_value = dummy_df
        self.mock_fred_fetcher.get_macro_context.return_value = {"status": "ok", "regime": "GOLDILOCKS"}

        # Initially cache is empty
        status = await self.repo.get_dxy_status()
        self.assertFalse(status["is_ready"])
        self.assertFalse(status["is_syncing"])

        # Trigger macro context fetch which starts DXY sync
        await self.repo.get_macro_context()

        # Give a small window for background task to start
        await asyncio.sleep(0.05)

        # Check syncing status
        status = await self.repo.get_dxy_status()
        self.assertTrue(status["is_syncing"] or status["is_ready"])

        # Wait for background task to complete
        for _ in range(10):
            if (await self.repo.get_dxy_status())["is_ready"]:
                break
            await asyncio.sleep(0.1)

        status = await self.repo.get_dxy_status()
        self.assertTrue(status["is_ready"])
        self.assertIsNotNone(await self.repo.get_dxy_data())
        print("SUCCESS: DXY loaded correctly after 'restart'")

    async def test_cache_refresh(self):
        """Regression: Cache refresh berjalan (expired cache)"""
        print("\nTesting: Cache refresh...")

        # Setup initial state
        old_df = pd.DataFrame({'Close': [90]}, index=pd.date_range('2025-01-01', periods=1))
        self.repo._macro_cache["dxy"] = old_df
        self.repo._macro_cache["data"] = {"status": "old"}
        self.repo._macro_cache["timestamp"] = time.time() - 1000 # Expired

        # New data
        new_df = pd.DataFrame({'Close': [100]}, index=pd.date_range('2026-01-01', periods=1))
        self.mock_fetcher.fetch.return_value = new_df
        self.mock_fred_fetcher.get_macro_context.return_value = {"status": "new"}

        # Trigger refresh
        await self.repo.get_macro_context()

        # Wait for background task
        for _ in range(10):
            dxy_data = await self.repo.get_dxy_data()
            if dxy_data.iloc[0]['Close'] == 100:
                break
            await asyncio.sleep(0.1)

        dxy_data = await self.repo.get_dxy_data()
        self.assertEqual(dxy_data.iloc[0]['Close'], 100)
        print("SUCCESS: Cache refreshed and stale data replaced")

    async def test_async_fetch_recovery(self):
        """Regression: Async fetch recover setelah failure"""
        print("\nTesting: Async fetch recovery after failure...")

        # Force cache to expire
        self.repo._macro_cache["timestamp"] = 0

        # First call fails for DXY (all 3 attempts mock failure)
        self.mock_fetcher.fetch.side_effect = [
            pd.DataFrame({'Close': [50]}), # Brent fetch success
            Exception("Network Error"),    # DXY fetch fails attempt 1
            Exception("Network Error"),    # DXY fetch fails attempt 2
            Exception("Network Error")     # DXY fetch fails attempt 3
        ]
        self.mock_fred_fetcher.get_macro_context.return_value = {"status": "ok"}

        await self.repo.get_macro_context()

        # Wait for failure to settle
        await asyncio.sleep(0.2)
        status = await self.repo.get_dxy_status()
        self.assertFalse(status["is_ready"])
        self.assertFalse(status["is_syncing"])

        # Second call succeeds
        self.repo._macro_cache["timestamp"] = 0 # Force expire again
        self.mock_fetcher.fetch.side_effect = [
            pd.DataFrame({'Close': [50]}), # Brent fetch success
            pd.DataFrame({'Close': [100]}) # DXY fetch success
        ]

        await self.repo.get_macro_context()

        # Wait for background task
        for _ in range(10):
            if (await self.repo.get_dxy_status())["is_ready"]:
                break
            await asyncio.sleep(0.1)

        status = await self.repo.get_dxy_status()
        self.assertTrue(status["is_ready"])
        self.assertEqual((await self.repo.get_dxy_data()).iloc[0]['Close'], 100)
        print("SUCCESS: Recovered after failure")

    async def test_concurrent_macro_calls(self):
        """Regression: Concurrent get_macro_context only triggers one DXY sync"""
        print("\nTesting: Concurrent macro calls...")

        # Setup mocks
        self.mock_fetcher.fetch.return_value = pd.DataFrame({'Close': [100]})
        self.mock_fred_fetcher.get_macro_context.return_value = {"status": "ok"}

        # We want to track how many times _sync_dxy_background is called.
        # Since it's an internal method called via create_task, we can patch it.
        with patch.object(StockRepository, '_sync_dxy_background', wraps=self.repo._sync_dxy_background) as mock_sync:
            # Call concurrently
            await asyncio.gather(
                self.repo.get_macro_context(),
                self.repo.get_macro_context(),
                self.repo.get_macro_context()
            )

            # Verify it was only called once
            # Note: Due to the lock in get_macro_context, they should wait for each other
            # and only the first one should see the cache as empty.
            self.assertEqual(mock_sync.call_count, 1)
            print(f"SUCCESS: _sync_dxy_background called {mock_sync.call_count} time(s)")

    async def test_dxy_status_integrity(self):
        """Regression: DXY status integrity during sync lifecycle"""
        print("\nTesting: DXY status integrity...")

        # Setup mocks with a bit of delay
        # We use a regular function because it's called in run_in_executor
        def slow_fetch(*args, **kwargs):
            time.sleep(0.1)
            return pd.DataFrame({'Close': [100]})

        self.mock_fetcher.fetch.side_effect = slow_fetch
        self.mock_fred_fetcher.get_macro_context.return_value = {"status": "ok"}

        # 1. Before sync
        status = await self.repo.get_dxy_status()
        self.assertFalse(status["is_ready"])
        self.assertFalse(status["is_syncing"])

        # 2. Start sync
        await self.repo.get_macro_context()

        # 3. During sync
        # Wait a bit for background task to start
        # Use a small sleep to let the event loop yield to the new task
        await asyncio.sleep(0.05)
        status = await self.repo.get_dxy_status()
        self.assertTrue(status["is_syncing"])
        self.assertFalse(status["is_ready"])

        # 4. After sync
        for _ in range(20):
            status = await self.repo.get_dxy_status()
            if status["is_ready"]:
                break
            await asyncio.sleep(0.05)

        status = await self.repo.get_dxy_status()
        self.assertTrue(status["is_ready"])
        self.assertFalse(status["is_syncing"])
        print("SUCCESS: Status transitioned correctly")

    async def test_network_latency_resilience(self):
        """REQ-6: Verify DXY fetch latency doesn't block macro context"""
        print("\nTesting: Network latency resilience...")

        # 1. Setup slow fetch (1.5s)
        def slow_fetch(*args, **kwargs):
            # Slow DXY fetch only
            if args and args[0] == "DX-Y.NYB":
                time.sleep(1.5)
            return pd.DataFrame({'Close': [100]})

        self.mock_fetcher.fetch.side_effect = slow_fetch
        self.mock_fred_fetcher.get_macro_context.return_value = {"status": "ok"}

        # 2. Call get_macro_context
        start_time = time.time()
        macro_context = await self.repo.get_macro_context()
        duration = time.time() - start_time

        # 3. Verify it returned immediately (DXY fetch is in background)
        self.assertLess(duration, 0.5, "get_macro_context should not be blocked by DXY fetch")
        self.assertEqual(macro_context["status"], "ok")

        # 4. Verify syncing state
        await asyncio.sleep(0.05)
        status = await self.repo.get_dxy_status()
        self.assertTrue(status["is_syncing"])

        # 5. Wait for DXY to complete
        # We need to wait longer than the 1.5s sleep
        for _ in range(30):
            if (await self.repo.get_dxy_status())["is_ready"]:
                break
            await asyncio.sleep(0.1)

        status = await self.repo.get_dxy_status()
        self.assertTrue(status["is_ready"])
        print("SUCCESS: Latency did not block main call and DXY eventually ready")

    async def test_data_corruption_recovery(self):
        """REQ-6: Verify recovery from corrupted/malformed DXY data"""
        print("\nTesting: Data corruption recovery...")

        # 1. First fetch returns corrupted data (empty DF) (all 3 attempts mock corrupted data)
        empty_df = pd.DataFrame()

        self.mock_fetcher.fetch.side_effect = [
            pd.DataFrame({'Close': [50]}), # Brent
            empty_df,                      # DXY corrupted (empty) attempt 1
            empty_df,                      # DXY corrupted (empty) attempt 2
            empty_df                       # DXY corrupted (empty) attempt 3
        ]
        self.mock_fred_fetcher.get_macro_context.return_value = {"status": "ok"}

        await self.repo.get_macro_context()

        # Wait for sync attempt to finish
        await asyncio.sleep(0.2)
        status = await self.repo.get_dxy_status()
        self.assertFalse(status["is_ready"], "Should not be ready with empty data")

        # 2. Next fetch returns valid data
        self.repo._macro_cache["timestamp"] = 0 # Force refresh
        valid_df = pd.DataFrame({'Close': [105]}, index=pd.date_range('2026-01-01', periods=1))

        self.mock_fetcher.fetch.side_effect = [
            pd.DataFrame({'Close': [50]}), # Brent
            valid_df                       # DXY valid
        ]

        await self.repo.get_macro_context()

        # Wait for sync to finish
        for _ in range(10):
            if (await self.repo.get_dxy_status())["is_ready"]:
                break
            await asyncio.sleep(0.1)

        status = await self.repo.get_dxy_status()
        self.assertTrue(status["is_ready"])
        data = await self.repo.get_dxy_data()
        self.assertEqual(data.iloc[0]['Close'], 105)
        print("SUCCESS: Recovered from corrupted data")

if __name__ == "__main__":
    unittest.main()
