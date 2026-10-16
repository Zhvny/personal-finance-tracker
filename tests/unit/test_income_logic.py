from decimal import Decimal

import pytest

from packages.core.application.income_service import IncomeService


@pytest.fixture
def income_service():
    # Mock repository as it's not needed for calculate_allocation logic
    return IncomeService(repository=None)

def test_calculate_allocation_basic(income_service):
    amount = Decimal("1000000")  # 1 Million
    result = income_service.calculate_allocation(amount)

    assert result["enabled"] is True
    assert result["income_amount"] == amount

    # Default rules: 50% expenses, 30% bank_savings, 10% investment, 10% emergency_fund
    buckets = {b["bucket"]: b["amount"] for b in result["buckets"]}

    assert buckets["expenses"] == Decimal("500000.00")
    assert buckets["bank_savings"] == Decimal("300000.00")
    assert buckets["investment"] == Decimal("100000.00")
    assert buckets["emergency_fund"] == Decimal("100000.00")

def test_calculate_allocation_zero_income(income_service):
    result = income_service.calculate_allocation(Decimal("0"))
    assert result["enabled"] is False
    assert result["income_amount"] == Decimal("0")

def test_calculate_allocation_rounding(income_service):
    # Test with an amount that might cause rounding issues
    amount = Decimal("1000000.33")
    result = income_service.calculate_allocation(amount)

    total_allocated = sum(b["amount"] for b in result["buckets"])
    # The sum of all buckets should exactly match the input amount
    # because the last bucket takes the remainder.
    assert total_allocated == amount

def test_calculate_allocation_custom_rules(income_service):
    amount = Decimal("1000")
    custom_rules = {
        "enabled": True,
        "rules": [
            {"bucket": "charity", "pct": 10},
            {"bucket": "savings", "pct": 90}
        ]
    }
    result = income_service.calculate_allocation(amount, rules=custom_rules)

    buckets = {b["bucket"]: b["amount"] for b in result["buckets"]}
    assert buckets["charity"] == Decimal("100.00")
    assert buckets["savings"] == Decimal("900.00")

