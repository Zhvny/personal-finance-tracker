from datetime import datetime
from unittest.mock import MagicMock, patch

from packages.core.infrastructure.persistence.postgres_expense_repository import (
    PostgresExpenseRepository,
)


def test_recurring_expenses_hold_a_transaction_scoped_advisory_lock():
    templates = [{
        "amount": 150_000,
        "description": "Subscription",
        "category": "other",
        "payment_method": "cash",
    }]
    cursor = MagicMock()
    cursor.fetchone.side_effect = [None, {"id": 12}]
    cursor.fetchall.return_value = templates
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    transaction = MagicMock()
    transaction.__enter__.return_value = connection

    with patch(
        "packages.core.infrastructure.persistence.postgres_expense_repository.DatabaseManager.transaction",
        return_value=transaction,
    ):
        result = PostgresExpenseRepository._apply_recurring_expenses_sync(
            datetime(2026, 8, 8, 9, 0, 0)
        )

    assert result == {
        "applied": 1,
        "skipped": 0,
        "entries": [{"id": 12, "description": "Subscription", "amount": 150_000.0}],
    }
    assert "pg_advisory_xact_lock" in cursor.execute.call_args_list[0].args[0]
    assert "INSERT INTO expenses" in cursor.execute.call_args_list[3].args[0]
