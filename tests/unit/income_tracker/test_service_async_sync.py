import os
import tempfile
from datetime import datetime
from decimal import Decimal

import pytest

from packages.core.application.income_service import IncomeService
from packages.core.infrastructure.income_tracker.repository import SQLiteIncomeRepository
from packages.database.index import run_query


@pytest.fixture
def temp_income_service():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    repo = SQLiteIncomeRepository(db_path=db_path)
    service = IncomeService(repo)
    yield service
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass

def test_income_service_sync_repo_integration(temp_income_service):
    # Test record_income via run_query
    res = run_query(temp_income_service.record_income(
        amount=Decimal("5000000"),
        source="Salary",
        income_type="salary",
        description="Monthly Salary",
        is_taxed=True
    ))
    assert res["income_id"] > 0
    assert res["is_real_income"] is True

    # Test get_incomes via run_query
    incomes = run_query(temp_income_service.get_incomes())
    assert len(incomes) == 1
    assert incomes[0].amount == Decimal("5000000")
    assert incomes[0].source == "Salary"

    # Test get_monthly_summary via run_query
    now = datetime.now()
    summary = run_query(temp_income_service.get_monthly_summary(now.year, now.month))
    assert summary["total"] == Decimal("5000000")
    assert summary["count"] == 1

    # Test delete_income via run_query
    deleted = run_query(temp_income_service.delete_income(res["income_id"]))
    assert deleted is True

    remaining = run_query(temp_income_service.get_incomes())
    assert len(remaining) == 0
