import pytest

pytestmark = pytest.mark.xfail(
    reason="Stability tests need real backend; tracked separately (tracking: gate-split)", strict=False
)
import gc
import sys
import tracemalloc
import unittest.mock as mock
from pathlib import Path


# Ensure root is in sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Add apps/cli to sys.path for direct module imports if needed by tui.py
CLI_PATH = ROOT / "apps" / "cli"
if str(CLI_PATH) not in sys.path:
    sys.path.insert(0, str(CLI_PATH))

# Import TUI components
from apps.cli.tui import DesktopTUI, MobileTUI


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_optimization_memory_stability(anyio_backend):
    """
    Stability & Regression Test for Portfolio Optimization.
    Ensures memory stability over repeated runs using tracemalloc.
    """
    # 1. Setup Mocks
    # Mock dashboard data to avoid DB dependencies and missing file errors
    mock_data = {
        "inc_this": 1000.0,
        "exp_this": 500.0,
        "bank_savings": 5000.0,
        "top_pred": {"ticker": "TEST", "target_price": 100.0, "pred_return": 5.0},
    }

    # Mock DatabaseManager if it's imported
    db_manager_path = "packages.core.infrastructure.persistence.postgres_manager.DatabaseManager"

    with (
        mock.patch("apps.cli.main._get_dashboard_data", return_value=mock_data),
        mock.patch("apps.cli.main.fmt", side_effect=lambda x: str(x)),
        mock.patch(f"{db_manager_path}.execute", return_value=None),
        mock.patch(f"{db_manager_path}.query", return_value=[]),
        mock.patch("apps.cli.genetic_optimizer.PortfolioOptimizer.save_results", return_value=None),
    ):
        # 2. Initialize TUI
        # DesktopTUI inherits from textual.app.App
        app = DesktopTUI()

        # Start tracemalloc
        tracemalloc.start()

        # Take initial snapshot after some warm-up (GC)
        gc.collect()
        snapshot_initial = tracemalloc.take_snapshot()

        memory_history = []
        num_runs = 10

        # 3. Execution Loop
        # run_test provides a simulated context for the Textual app
        async with app.run_test() as pilot:
            for i in range(num_runs):
                # We directly call the async optimization method
                await app.run_portfolio_optimization()

                # Cleanup and record
                gc.collect()
                current_mem = tracemalloc.get_traced_memory()[0] / (1024 * 1024)  # MB
                memory_history.append(current_mem)

        # 4. Final Snapshot and Analysis
        snapshot_final = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snapshot_final.compare_to(snapshot_initial, "lineno")
        total_growth_bytes = sum(stat.size_diff for stat in stats)
        total_growth_mb = total_growth_bytes / (1024 * 1024)

        # 5. Theme/Layout Switch Simulation
        mobile_app = MobileTUI()
        async with mobile_app.run_test() as pilot:
            # Re-running optimization in different layout
            await mobile_app.run_portfolio_optimization()

        # 6. Assertions
        # Threshold: < 5MB growth after 10 runs of a genetic optimizer
        assert total_growth_mb < 5.0, f"Memory leak detected! Total growth: {total_growth_mb:.2f} MB"

        # Trend check: Ensure memory doesn't just keep going up significantly
        if len(memory_history) > 1:
            growth_trend = memory_history[-1] - memory_history[0]
            assert growth_trend < 3.0, f"Upward memory trend detected: {growth_trend:.2f} MB"


if __name__ == "__main__":
    # If run directly, use pytest to handle the async test
    sys.exit(pytest.main([__file__, "-s"]))
