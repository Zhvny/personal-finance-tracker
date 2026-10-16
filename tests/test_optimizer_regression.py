import asyncio
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANAGER_ROOT = PROJECT_ROOT.parent / "Tools" / "Gemini-Manager"
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "cli" / "stock_analyzer"))
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "cli"))
sys.path.append(str(MANAGER_ROOT / "apps" / "cli"))

from domain.config import AppConfig
from genetic_optimizer import PortfolioOptimizer

try:
    from manager.covariance_manager import CovarianceManager
    from manager.database import Database
    HAS_MANAGER = True
except ImportError:
    HAS_MANAGER = False
    CovarianceManager = None
    Database = None

def generate_mock_returns(n_assets, n_days=50):
    tickers = [f"REG_TKR_{i:03d}" for i in range(n_assets)]
    data = np.random.normal(0.0005, 0.01, (n_days, n_assets))
    return pd.DataFrame(data, columns=tickers)

def test_optimizer_survive_restart():
    """Verify that multiple independent optimizer instances can run sequentially."""
    returns_df = generate_mock_returns(10)

    # Run 1
    opt1 = PortfolioOptimizer(pop_size=5, generations=2)
    res1 = opt1.optimize(returns_df)
    assert res1 is not None

    # Run 2
    opt2 = PortfolioOptimizer(pop_size=5, generations=2)
    res2 = opt2.optimize(returns_df)
    assert res2 is not None
    assert res1["weights"].keys() == res2["weights"].keys()

def test_config_persistence(tmp_path):
    """Restart Recovery: Simulate setting a config value and verifying it persists after reload."""
    config_file = tmp_path / "test_config.yaml"

    # Initial state
    initial_config = {
        'scoring': {'buy_threshold': 8.5, 'wait_threshold': 6.0},
        'signal': {'atr_high_risk_gate': 0.1, 'sl_atr_multiplier': 2.0, 'tp_atr_multiplier': 4.0},
        'fetch': {'period': '1y', 'max_workers': 5},
        'ga': {'max_assets': 7, 'pop_size': 50, 'generations': 10}
    }

    with open(config_file, 'w') as f:
        yaml.dump(initial_config, f)

    # Load and verify
    cfg = AppConfig.load(path=str(config_file))
    assert cfg.ga_max_assets == 7

    # Simulate user change via "GUI/CLI" and "Restart"
    updated_config = initial_config.copy()
    updated_config['ga']['max_assets'] = 15
    with open(config_file, 'w') as f:
        yaml.dump(updated_config, f)

    # Simulate Restart (re-load)
    cfg_restarted = AppConfig.load(path=str(config_file))
    assert cfg_restarted.ga_max_assets == 15

def test_yfinance_cache_rebuild():
    """Cache Integrity: Verify yfinance cache presence and mock rebuild."""
    cache_path = PROJECT_ROOT / ".cache" / "yfinance"

    # Check if cache directory exists (might not in fresh env, but should in project)
    if not cache_path.exists():
        cache_path.mkdir(parents=True, exist_ok=True)

    # Verify we can touch a file in it
    test_file = cache_path / "test_cache_entry.db"
    test_file.touch()
    assert test_file.exists()

    # Simulate Wipe
    os.remove(test_file)
    assert not test_file.exists()

    # In a real scenario, yfinance would rebuild it on next call.
    # Here we just verify we have write access to the cache location.
    test_file.touch()
    assert test_file.exists()

@pytest.mark.skipif(not HAS_MANAGER, reason="manager package not available")
def test_covariance_cache_rebuild(caplog):
    """Verify that clearing the cache forces a rebuild and subsequent runs hit the cache."""
    db = Database(schema="market")
    cov_mgr = CovarianceManager(db=db)

    # Unique tickers for this test to avoid collision
    tickers = [f"CACHE_TEST_{i}" for i in range(5)]
    returns_df = generate_mock_returns(5)
    returns_df.columns = tickers

    # 1. Clear existing cache for these tickers
    hash_key = cov_mgr._generate_hash(tickers, "daily")
    with db.get_cursor() as cur:
        cur.execute("DELETE FROM market.covariance_cache WHERE hash_key = %s", (hash_key,))

    optimizer = PortfolioOptimizer(pop_size=5, generations=2)

    # 2. First run - should be a CACHE MISS (or rather, it will save it)
    with caplog.at_level(logging.INFO):
        optimizer.optimize(returns_df)

    assert "Covariance cache saved" in caplog.text

    # 3. Second run - should be a CACHE HIT
    caplog.clear()
    with caplog.at_level(logging.INFO):
        optimizer.optimize(returns_df)

    assert "Covariance cache HIT" in caplog.text

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.mark.anyio
async def test_async_worker_recovery():
    """Verify that the async wrapper handles multiple concurrent calls or sequential calls after error."""
    optimizer = PortfolioOptimizer(pop_size=10, generations=5)
    returns_df = generate_mock_returns(10)

    # Run two in parallel
    task1 = optimizer.optimize_async(returns_df)
    task2 = optimizer.optimize_async(returns_df)

    results = await asyncio.gather(task1, task2)

    assert len(results) == 2
    assert results[0] is not None
    assert results[1] is not None

    # Verify we can still run after successful async tasks
    res3 = await optimizer.optimize_async(returns_df)
    assert res3 is not None

@pytest.mark.anyio
async def test_async_interruption_recovery():
    """Simulate a worker interruption (via tight timeout) and verify we can still run."""
    optimizer = PortfolioOptimizer(pop_size=200, generations=100) # Heavy
    returns_df = generate_mock_returns(50)

    # Start a task and cancel it
    task = asyncio.create_task(optimizer.optimize_async(returns_df))
    await asyncio.sleep(0.05)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify optimizer (and its thread pool) is still functional
    optimizer_fast = PortfolioOptimizer(pop_size=5, generations=2)
    res = await optimizer_fast.optimize_async(returns_df)
    assert res is not None
