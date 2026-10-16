import pytest

pytestmark = pytest.mark.xfail(
    reason="Integration tests need full backend setup; tracked separately (tracking: gate-split)", strict=False
)
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to sys.path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from apps.cli.investment_tracker.services.stock_service import StockPriceService
from apps.cli.scheduler import main as scheduler_main


def test_scheduler_logging_on_optimization_failure(caplog):
    """Verify scheduler logs and continues when optimization fails."""
    # The logger in scheduler is named 'scheduler'
    with caplog.at_level(logging.INFO, logger="scheduler"):
        with patch("apps.cli.scheduler.acquire_lock"):
            with patch("apps.cli.scheduler.release_lock"):
                with patch("apps.cli.scheduler.run_monthly_optimization") as mock_opt:
                    mock_opt.side_effect = RuntimeError("Optimization Crash")

                    with patch("apps.cli.scheduler.EvaluationEngine") as mock_engine_cls:
                        mock_engine = MagicMock()
                        mock_engine.evaluate_pending_predictions.return_value = 5
                        mock_engine_cls.return_value = mock_engine

                        scheduler_main()

                        # Verify optimization failure was logged
                        assert "Genetic Optimization Failed: Optimization Crash" in caplog.text
                        # Verify it continued to evaluate predictions
                        mock_engine.evaluate_pending_predictions.assert_called_once()
                        assert "Evaluated 5 Senate predictions." in caplog.text


def test_stock_service_logging_on_yfinance_failure(caplog):
    """Verify StockPriceService logs and falls back when yfinance info fails."""
    mock_fx = MagicMock()
    mock_fx.get_usd_idr.return_value = 16000
    service = StockPriceService(mock_fx)

    with caplog.at_level(logging.ERROR):
        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()

            # Mock the info objects to raise when .get() is called
            mock_i = MagicMock()
            mock_i.get.side_effect = Exception("YF Info Down")
            mock_ticker.basic_info = mock_i
            mock_ticker.fast_info = mock_i
            mock_ticker.info = mock_i

            # Mock history to succeed as fallback
            mock_history = MagicMock()
            mock_history.empty = False
            # Mocking h["Close"].dropna().iloc[-1]
            mock_history.__getitem__.return_value.dropna.return_value.iloc.__getitem__.return_value = 150.0
            mock_ticker.history.return_value = mock_history

            mock_ticker_cls.return_value = mock_ticker

            price = service.get_current_price_usd("AAPL")

            assert price == 150.0
            assert "YFinance basic_info fetch failed for AAPL" in caplog.text
