# services/sell_service.py
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional

from packages.core.domain.models import Investment, InvestmentStatus


@dataclass
class SellResult:
    quantity_sold: Decimal
    sell_value_idr: Decimal
    buy_value_idr: Decimal
    realized_pl: Decimal
    realized_pl_pct: Decimal
    remaining: Decimal
    is_fully_sold: bool
    lot_details: List[Dict] = field(default_factory=list)
    # Raw values for high-precision summation in FIFO
    sell_value_idr_raw: Decimal = Decimal("0")
    buy_value_idr_raw: Decimal = Decimal("0")
    # Original-currency P/L (set when sell_currency != IDR)
    realized_pl_usd: Optional[Decimal] = None
    sell_currency: str = "IDR"


class SellService:
    def __init__(self, fx_service):
        self.fx_service = fx_service

    def execute_sell(self, investment: Investment,
                     quantity: Decimal,
                     sell_price: Decimal,
                     sell_currency: str = "IDR",
                     sell_date: Optional[datetime] = None,
                     fees: Decimal = Decimal("0"),
                     quantize: bool = True) -> SellResult:

        # Ensure inputs are Decimal and quantized
        quantity = Decimal(str(quantity)).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)
        sell_price = Decimal(str(sell_price))
        fees = Decimal(str(fees))

        if quantity > investment.remaining_quantity:
            raise ValueError(f"Cannot sell {quantity}, only {investment.remaining_quantity} remaining")

        sell_date = sell_date or datetime.now()

        # Normalize to IDR
        if sell_currency.upper() == "USD":
            usd_idr = Decimal(str(self.fx_service.get_usd_idr()))
            sell_price_idr = (sell_price * usd_idr)
        else:
            sell_price_idr = sell_price

        # Cost basis (buy price in IDR) - Use stored buy_price_idr if available
        if investment.buy_price_idr is not None:
            buy_price_idr = investment.buy_price_idr
        elif investment.buy_currency.upper() == "USD":
            # Fallback for old records if buy_price_idr is missing
            usd_idr = Decimal(str(self.fx_service.get_usd_idr()))
            buy_price_idr = (investment.buy_price * usd_idr)
        else:
            buy_price_idr = investment.buy_price

        # Calculate raw realized P/L
        sell_value_idr_raw = (sell_price_idr * quantity)
        buy_value_idr_raw = (buy_price_idr * quantity)
        realized_pl_raw = (sell_value_idr_raw - buy_value_idr_raw - fees)

        # Apply quantization if requested (IDR = 0 decimal places)
        target = Decimal('1')
        if quantize:
            sell_value_idr = sell_value_idr_raw.quantize(target, rounding=ROUND_HALF_UP)
            buy_value_idr = buy_value_idr_raw.quantize(target, rounding=ROUND_HALF_UP)
            fees = fees.quantize(target, rounding=ROUND_HALF_UP)
            realized_pl = (sell_value_idr - buy_value_idr - fees)
        else:
            sell_value_idr = sell_value_idr_raw
            buy_value_idr = buy_value_idr_raw
            realized_pl = realized_pl_raw

        realized_pl_pct = ((realized_pl / buy_value_idr * 100) if buy_value_idr else Decimal("0")).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Update investment
        investment.remaining_quantity = (investment.remaining_quantity - quantity).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)

        if investment.remaining_quantity <= Decimal("0"):
            investment.remaining_quantity = Decimal("0")
            investment.status = InvestmentStatus.SOLD
        else:
            investment.status = InvestmentStatus.PARTIAL_SOLD

        # Compute original-currency P/L for display when sold in USD
        realized_pl_usd: Optional[Decimal] = None
        if sell_currency.upper() == "USD":
            buy_price_usd: Decimal
            if investment.buy_currency.upper() == "USD":
                buy_price_usd = investment.buy_price
            else:
                usd_idr = Decimal(str(self.fx_service.get_usd_idr()))
                buy_price_usd = (buy_price_idr / usd_idr) if usd_idr else Decimal("0")
            sell_value_usd = sell_price * quantity
            buy_value_usd = buy_price_usd * quantity
            realized_pl_usd = (sell_value_usd - buy_value_usd - (fees / Decimal(str(self.fx_service.get_usd_idr())) if self.fx_service.get_usd_idr() else Decimal("0")))

        return SellResult(
            quantity_sold=quantity,
            sell_value_idr=sell_value_idr,
            buy_value_idr=buy_value_idr,
            realized_pl=realized_pl,
            realized_pl_pct=realized_pl_pct,
            remaining=investment.remaining_quantity,
            is_fully_sold=(investment.remaining_quantity <= Decimal("0")),
            sell_value_idr_raw=sell_value_idr_raw,
            buy_value_idr_raw=buy_value_idr_raw,
            realized_pl_usd=realized_pl_usd,
            sell_currency=sell_currency.upper()
        )

    def execute_fifo_sell(self, lots: List[Investment],
                          quantity: Decimal,
                          sell_price: Decimal,
                          sell_currency: str = "IDR",
                          sell_date: Optional[datetime] = None,
                          fees: Decimal = Decimal("0")) -> SellResult:
        """
        Execute a sell using First-In-First-Out logic across multiple lots.
        """
        # Ensure inputs are Decimal and quantized
        quantity = Decimal(str(quantity)).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)
        sell_price = Decimal(str(sell_price))
        fees = Decimal(str(fees))

        total_remaining_in_lots = sum(lot.remaining_quantity for lot in lots)
        if quantity > total_remaining_in_lots:
            raise ValueError(f"Cannot sell {quantity}, only {total_remaining_in_lots} total units available across {len(lots)} lots.")

        # Ensure lots are sorted by date
        sorted_lots = sorted(lots, key=lambda x: x.buy_date or datetime.min)

        remaining_to_sell = quantity
        total_sell_value_idr_raw = Decimal("0")
        total_buy_value_idr_raw = Decimal("0")
        lot_details = []

        sell_date = sell_date or datetime.now()

        for lot in sorted_lots:
            if remaining_to_sell <= Decimal("0"):
                break

            if lot.remaining_quantity <= Decimal("0"):
                continue

            qty_from_this_lot = min(remaining_to_sell, lot.remaining_quantity).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)

            # Distribute fees proportionally (raw)
            lot_fees = ((qty_from_this_lot / quantity) * fees)

            # Execute sell on this specific lot (don't quantize yet to avoid drift)
            res = self.execute_sell(
                lot, qty_from_this_lot, sell_price,
                sell_currency, sell_date, fees=lot_fees,
                quantize=False
            )

            total_sell_value_idr_raw += res.sell_value_idr_raw
            total_buy_value_idr_raw += res.buy_value_idr_raw

            lot_details.append({
                "lot_id": lot.id,
                "qty": qty_from_this_lot,
                "buy_price_idr": lot.buy_price_idr,
                "realized_pl": res.realized_pl, # This will be raw realized_pl
                "realized_pl_pct": res.realized_pl_pct,
                "realized_pl_usd": res.realized_pl_usd,
                "fees": lot_fees,
                "investment": lot # Pass back the updated lot object
            })

            remaining_to_sell -= qty_from_this_lot

        # Final quantization for reporting (IDR = 0 decimal places)
        target = Decimal('1')
        total_sell_value_idr = total_sell_value_idr_raw.quantize(target, rounding=ROUND_HALF_UP)
        total_buy_value_idr = total_buy_value_idr_raw.quantize(target, rounding=ROUND_HALF_UP)
        final_fees = fees.quantize(target, rounding=ROUND_HALF_UP)
        total_realized_pl = (total_sell_value_idr - total_buy_value_idr - final_fees)

        total_pl_pct = ((total_realized_pl / total_buy_value_idr * 100) if total_buy_value_idr else Decimal("0")).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Sum USD P/L from individual lot results if available
        realized_pl_usd_total: Optional[Decimal] = None
        if sell_currency.upper() == "USD":
            realized_pl_usd_total = sum(
                (detail.get("realized_pl_usd") or Decimal("0"))
                for detail in lot_details
                if detail.get("realized_pl_usd") is not None
            )

        return SellResult(
            quantity_sold=quantity,
            sell_value_idr=total_sell_value_idr,
            buy_value_idr=total_buy_value_idr,
            realized_pl=total_realized_pl,
            realized_pl_pct=total_pl_pct,
            remaining=(total_remaining_in_lots - quantity).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP),
            is_fully_sold=(total_remaining_in_lots - quantity <= Decimal("0")),
            lot_details=lot_details,
            realized_pl_usd=realized_pl_usd_total,
            sell_currency=sell_currency.upper()
        )
