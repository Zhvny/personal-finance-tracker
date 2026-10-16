import time
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from apps.cli.investment_tracker.services.sell_service import SellService
from packages.core.domain.models.investment import Investment, InvestmentStatus


def test_high_volume_fifo_precision():
    """
    Stress test: 10,000 buy lots followed by 1 massive FIFO sell.
    Verifies that Decimal precision prevents drift and latency is acceptable.
    """
    fx_mock = MagicMock()
    fx_mock.get_usd_idr.return_value = 16000.0

    sell_service = SellService(fx_mock)

    # Generate 10,000 lots
    # Using 'messy' values to invite floating point drift
    # Price: 1000.33, Quantity: 0.00012345
    # Value per lot: 0.1234907315 USD
    num_lots = 10000
    ticker = "BTC"
    buy_price_usd = Decimal("1000.33")
    qty_per_lot = Decimal("0.00012345")

    lots = []
    base_date = datetime(2023, 1, 1)

    for i in range(num_lots):
        lots.append(
            Investment(
                id=i,
                ticker=ticker,
                asset_type="crypto",
                quantity=qty_per_lot,
                remaining_quantity=qty_per_lot,
                buy_price=buy_price_usd,
                buy_currency="USD",
                buy_price_idr=buy_price_usd * Decimal("16000"),
                buy_date=base_date + timedelta(minutes=i),
                status=InvestmentStatus.HOLDING,
            )
        )

    total_qty = qty_per_lot * num_lots
    sell_price_usd = Decimal("2000.66")  # Exactly double

    # Expected P/L per lot (raw):
    # Buy IDR: 1000.33 * 16000 * 0.00012345 = 16005280 * 0.00012345 = 1975.851824
    # Sell IDR: 2000.66 * 16000 * 0.00012345 = 32010560 * 0.00012345 = 3951.703648
    # P/L IDR (raw): 1975.851824

    # Total P/L (raw): 1975.851824 * 10000 = 19758518.24
    # quantized to IDR (0 decimal places) = 19758518

    start_time = time.time()

    result = sell_service.execute_fifo_sell(
        lots=lots, quantity=total_qty, sell_price=sell_price_usd, sell_currency="USD", fees=Decimal("0")
    )

    end_time = time.time()
    latency = end_time - start_time

    # Assertions
    # Total Buy IDR (raw): 19758518.24 -> quantized 19758518
    # Total Sell IDR (raw): 39517036.48 -> quantized 39517036
    # P/L = 39517036 - 19758518 = 19758518

    assert result.quantity_sold == total_qty
    assert result.is_fully_sold is True
    assert result.realized_pl == Decimal("19758518")

    # Benchmark check: < 2 seconds for 10k lots
    print("\nStability Test Results:")
    print(f"Lots Processed: {num_lots}")
    print(f"Latency: {latency:.4f}s")

    assert latency < 2.0, f"FIFO sell too slow: {latency:.4f}s"


if __name__ == "__main__":
    test_high_volume_fifo_precision()
