from datetime import datetime
from decimal import Decimal

from packages.core.domain.models.investment import Investment


def test_investment_validation_with_null_sells():
    # Simulate a database row or dict where the 'sells' relationship is None
    row = {
        "id": 1,
        "asset_type": "stock",
        "ticker": "AAPL",
        "quantity": Decimal("10.0"),
        "buy_price": Decimal("150.0"),
        "buy_currency": "USD",
        "buy_price_idr": Decimal("2400000.0"),
        "buy_date": datetime.now(),
        "status": "holding",
        "remaining_quantity": Decimal("10.0"),
        "is_favorite": False,
        "sells": None  # This is what was causing the backend error (500)
    }

    # Validate the dictionary to recreate the scenario
    inv = Investment.model_validate(row)

    # Verify that 'sells' was successfully converted to an empty list
    assert inv.sells == []
    assert inv.ticker == "AAPL"
    assert inv.quantity == Decimal("10.0")

def test_investment_validation_with_missing_sells():
    # Simulate a dictionary where 'sells' is completely missing
    row = {
        "id": 1,
        "asset_type": "stock",
        "ticker": "MSFT",
        "quantity": Decimal("5.0"),
        "buy_price": Decimal("300.0"),
        "buy_currency": "USD",
        "buy_price_idr": Decimal("4800000.0"),
        "buy_date": datetime.now(),
        "status": "holding",
        "remaining_quantity": Decimal("5.0"),
        "is_favorite": False
    }

    inv = Investment.model_validate(row)
    assert inv.sells == []
    assert inv.ticker == "MSFT"
