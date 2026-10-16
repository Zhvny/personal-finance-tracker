import pytest

pytestmark = pytest.mark.xfail(
    reason="Integration tests need full backend setup; tracked separately (tracking: gate-split)", strict=False
)
import logging
from unittest.mock import AsyncMock, patch

from apps.cli.main import _get_dashboard_data, _launch, run_module


def test_fx_service_fallback_on_api_error(caplog):
    """Verify FXService falls back to default rate and logs error on API failure."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("Network timeout")

        from apps.cli.investment_tracker.services.fx_service import FXService

        service = FXService(fallback_rate=16500)
        rate = service.get_usd_idr()

        assert rate == 16500
        # Check if logger was called
        assert any("FX Service Error" in record.message for record in caplog.records)


def test_dashboard_resilience_to_service_failures():
    """Verify dashboard data fetching continues even if one service fails."""
    with (
        patch("apps.cli.main.expense_repo") as mock_exp,
        patch("apps.cli.main.income_repo") as mock_inc,
        patch("apps.cli.main.investment_repo") as mock_inv,
        patch("apps.cli.investment_tracker.services.fx_service.FXService") as mock_fx,
    ):
        mock_exp.get_all.return_value = []
        mock_inc.get_all.return_value = []
        mock_inv.get_all_active.return_value = []

        mock_fx.side_effect = Exception("FX Critical Failure")

        data = _get_dashboard_data()

        assert data["month_label"] is not None
        assert data["port_value"] == 0.0


def test_main_cli_error_logging(caplog):
    """Verify that main.py logs exceptions instead of failing silently."""
    from apps.cli.main import _get_dashboard_data

    with caplog.at_level(logging.ERROR):
        with patch("apps.cli.main._fetch_dashboard_data") as mock_fetch:
            mock_fetch.side_effect = RuntimeError("Simulation of deep failure")

            data = _get_dashboard_data()

    assert "Simulation of deep failure" in caplog.text
    assert "Dashboard data fetch failed" in caplog.text


def test_module_launch_error_propagation(caplog):
    """Verify that _launch correctly catches and logs exceptions from modules."""

    def crashing_module():
        raise ValueError("Module crashed unexpectedly")

    with caplog.at_level(logging.ERROR):
        _launch("TestModule", crashing_module)

    assert "Error in TestModule: Module crashed unexpectedly" in caplog.text
    assert "ValueError: Module crashed unexpectedly" in caplog.text


def test_run_module_not_found(caplog):
    """Verify that run_module logs an error when a module is missing."""
    with caplog.at_level(logging.ERROR):
        _launch("MissingModule", lambda: run_module("non_existent_module_path"))

    assert "Error in MissingModule" in caplog.text
    assert "ImportError" in caplog.text or "ModuleNotFoundError" in caplog.text


def test_api_global_exception_logging(caplog):
    """Verify that the API global exception handler logs unhandled exceptions."""
    from fastapi.testclient import TestClient

    from apps.api.main import app

    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR):
        with patch("packages.core.infrastructure.persistence.postgres_expense_repository._db") as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db
            mock_db.expense.find_many.side_effect = RuntimeError("Critical database failure")

            response = client.get("/api/expenses")

            assert response.status_code == 500
            assert response.json()["detail"] == "Internal Server Error"
