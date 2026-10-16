from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from apps.cli.investment_tracker.services.sell_service import SellService
from packages.core.domain.models import Investment, InvestmentStatus


class MockFXService:
    def get_usd_idr(self):
        return Decimal("15000.0")

@pytest.fixture
def sell_service():
    return SellService(MockFXService())

def test_fifo_sell_multiple_lots(sell_service):
    # Setup 3 lots of AAPL
    # Lot 1: 10 units at $150 (Oldest)
    lot1 = Investment(
        id=1,
        asset_type="stock",
        ticker="AAPL",
        quantity=Decimal("10.0"),
        buy_price=Decimal("150.0"),
        buy_currency="USD",
        buy_date=datetime.now() - timedelta(days=30),
        buy_price_idr=Decimal("150.0") * Decimal("15000.0")
    )
    # Lot 2: 10 units at $160
    lot2 = Investment(
        id=2,
        asset_type="stock",
        ticker="AAPL",
        quantity=Decimal("10.0"),
        buy_price=Decimal("160.0"),
        buy_currency="USD",
        buy_date=datetime.now() - timedelta(days=20),
        buy_price_idr=Decimal("160.0") * Decimal("15000.0")
    )
    # Lot 3: 10 units at $170 (Newest)
    lot3 = Investment(
        id=3,
        asset_type="stock",
        ticker="AAPL",
        quantity=Decimal("10.0"),
        buy_price=Decimal("170.0"),
        buy_currency="USD",
        buy_date=datetime.now() - timedelta(days=10),
        buy_price_idr=Decimal("170.0") * Decimal("15000.0")
    )

    # Lots passed in out-of-order to test internal sorting
    lots = [lot3, lot1, lot2]

    # Sell 15 units at $180
    result = sell_service.execute_fifo_sell(
        lots=lots,
        quantity=Decimal("15.0"),
        sell_price=Decimal("180.0"),
        sell_currency="USD"
    )

    # Assertions
    assert result.quantity_sold == Decimal("15.0")
    assert len(result.lot_details) == 2

    # Lot 1 should be fully sold (10 units)
    assert result.lot_details[0]["lot_id"] == 1
    assert result.lot_details[0]["qty"] == Decimal("10.0")
    assert lot1.remaining_quantity == Decimal("0")
    assert lot1.status == InvestmentStatus.SOLD

    # Lot 2 should be partially sold (5 units)
    assert result.lot_details[1]["lot_id"] == 2
    assert result.lot_details[1]["qty"] == Decimal("5.0")
    assert lot2.remaining_quantity == Decimal("5.0")
    assert lot2.status == InvestmentStatus.PARTIAL_SOLD

    # Lot 3 should be untouched
    assert lot3.remaining_quantity == Decimal("10.0")
    assert lot3.status == InvestmentStatus.HOLDING

def test_sell_more_than_owned(sell_service):
    lot1 = Investment(
        id=1,
        asset_type="stock",
        ticker="AAPL",
        quantity=Decimal("10.0"),
        buy_price=Decimal("150.0"),
        buy_currency="USD",
        buy_price_idr=Decimal("150.0") * Decimal("15000.0")
    )

    with pytest.raises(ValueError, match="total units available"):
        sell_service.execute_fifo_sell(
            lots=[lot1],
            quantity=Decimal("15.0"),
            sell_price=Decimal("180.0")
        )

def test_pl_calculation_usd(sell_service):
    # 1 unit at $100, sell at $150. FX = 15000
    # Buy IDR = 1,500,000
    # Sell IDR = 2,250,000
    # P/L = 750,000 (50%)
    lot = Investment(
        id=1,
        asset_type="stock",
        ticker="TEST",
        quantity=Decimal("1.0"),
        buy_price=Decimal("100.0"),
        buy_currency="USD",
        buy_price_idr=Decimal("1500000.0")
    )

    result = sell_service.execute_fifo_sell(
        lots=[lot],
        quantity=Decimal("1.0"),
        sell_price=Decimal("150.0"),
        sell_currency="USD"
    )

    assert result.realized_pl == Decimal("750000")
    assert result.realized_pl_pct == Decimal("50.00")
