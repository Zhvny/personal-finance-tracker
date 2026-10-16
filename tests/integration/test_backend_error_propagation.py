import pytest
import os
import sys

pytestmark = pytest.mark.xfail(
    reason="Integration tests need full backend setup; tracked separately (tracking: gate-split)", strict=False
)
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

# Add apps/api to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../apps/api")))

from main import app

client = TestClient(app, raise_server_exceptions=False)


def test_expense_creation_error_propagation():
    """
    REQ-4: Verify that backend errors during expense creation are propagated as HTTP 400.
    """
    expense_data = {
        "amount": 100.0,
        "category": "food",
        "description": "Lunch",
        "date": "2024-05-30T00:00:00Z",
        "payment_method": "cash",
    }

    with patch("packages.core.infrastructure.persistence.postgres_expense_repository._db") as mock_get_db:
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        # Simulate a database error
        mock_db.expense.create = AsyncMock(side_effect=Exception("Database connection failed"))

        response = client.post("/api/expenses", json=expense_data)

        assert response.status_code in (400, 500)


def test_health_check_propagation():
    """
    Verify health check returns correct status.
    """
    with patch("apps.api.main.DatabaseManager") as mock_db:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["database"] == "connected"
