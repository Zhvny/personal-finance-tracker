"""DEPRECATED: SQLite Decimal precision check.

SQLite REAL storage is not canonical — exact money precision is only valid on
Postgres (DECIMAL columns via Prisma Decimal). Use the Postgres Decimal
round-trip test in tests/regression/test_prisma_float_serialization.py instead.
This script is kept for manual SQLite debugging only.
"""
import os
import sys
import warnings
from decimal import Decimal

import pytest

pytestmark = pytest.mark.skip(reason="deprecated: SQLite precision is not canonical; see Postgres Decimal round-trip test")

warnings.warn(
    "scripts/verify_decimal_repo.py is deprecated: SQLite precision is not canonical (Postgres DECIMAL only)",
    DeprecationWarning,
    stacklevel=2,
)

# Add project root to path
sys.path.append(os.getcwd())

from datetime import datetime

from packages.core.domain.models.investment import Investment, InvestmentStatus
from packages.core.infrastructure.investment_tracker.sqlite_repository import SQLiteInvestmentRepository


def test_decimal_persistence():
    repo = SQLiteInvestmentRepository("data/test_decimal.db")

    # Create test investment
    inv = Investment(
        asset_type="stock",
        ticker="TEST",
        quantity=Decimal("10.55555555"),
        buy_price=Decimal("100.12345678"),
        buy_currency="USD",
        buy_date=datetime.now(),
        status=InvestmentStatus.HOLDING
    )

    inv_id = repo.save(inv)
    print(f"Saved investment ID: {inv_id}")

    # Retrieve
    retrieved = repo.get_by_id(inv_id)

    print(f"Quantity type: {type(retrieved.quantity)}")
    print(f"Quantity value: {retrieved.quantity}")

    assert isinstance(retrieved.quantity, Decimal), "Quantity should be Decimal"
    assert retrieved.quantity == Decimal("10.55555555"), "Value should be exactly 10.55555555"

    # Check addition precision
    result = retrieved.quantity + Decimal("0.1")
    print(f"10.55555555 + 0.1 = {result}")
    assert result == Decimal("10.65555555")

    print("Verification PASSED")

    # Cleanup
    if os.path.exists("data/test_decimal.db"):
        os.remove("data/test_decimal.db")

if __name__ == "__main__":
    test_decimal_persistence()
