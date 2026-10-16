from datetime import datetime
from decimal import Decimal

from investment_tracker.services.sell_service import SellService

from packages.core.domain.models.investment import Investment, InvestmentStatus


class MockFxService:
    def get_usd_idr(self):
        return Decimal("16000.0")

def test_fifo_sell_precision_and_lot_tracking():
    """
    Test FIFO sell logic with Decimal precision and multiple lots.
    """
    fx_service = MockFxService()
    sell_service = SellService(fx_service)

    # Setup lots
    lot1 = Investment(
        id=1,
        asset_type="STOCK",
        ticker="AAPL",
        quantity=Decimal("10.5"),
        buy_price=Decimal("150.0"),
        buy_currency="USD",
        buy_date=datetime(2026, 1, 1),
    )
    # Mocking buy_price_idr which is usually enriched by repository
    lot1.buy_price_idr = Decimal("2400000.0") # 150 * 16000

    lot2 = Investment(
        id=2,
        asset_type="STOCK",
        ticker="AAPL",
        quantity=Decimal("5.0"),
        buy_price=Decimal("160.0"),
        buy_currency="USD",
        buy_date=datetime(2026, 2, 1),
    )
    lot2.buy_price_idr = Decimal("2560000.0") # 160 * 16000

    lots = [lot1, lot2]

    # Sell 12 units (should take all of lot1 and 1.5 from lot2)
    sell_qty = Decimal("12.0")
    sell_price_usd = Decimal("180.0")

    result = sell_service.execute_fifo_sell(
        lots=lots,
        quantity=sell_qty,
        sell_price=sell_price_usd,
        sell_currency="USD",
        fees=Decimal("10.0")
    )

    # Verification
    assert result.quantity_sold == sell_qty
    assert isinstance(result.realized_pl, Decimal), f"Realized PL should be Decimal, got {type(result.realized_pl)}"

    # Lot 1 should be fully sold
    assert lot1.remaining_quantity == Decimal("0")
    assert lot1.status == InvestmentStatus.SOLD

    # Lot 2 should have 3.5 remaining
    assert lot2.remaining_quantity == Decimal("3.5")
    assert lot2.status == InvestmentStatus.PARTIAL_SOLD

    # Precise PL calculation
    # Sell Value IDR: 12 * 180 * 16000 = 34,560,000
    # Buy Value IDR:
    #   Lot 1: 10.5 * 150 * 16000 = 25,200,000
    #   Lot 2: 1.5 * 160 * 16000 = 3,840,000
    #   Total Buy: 29,040,000
    # Realized PL: 34,560,000 - 29,040,000 - 10 = 5,519,990
    assert result.realized_pl == Decimal("5519990.0")
