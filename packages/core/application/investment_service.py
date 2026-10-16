import inspect
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

from packages.core.domain.models.investment import Investment, InvestmentStatus, SellTransaction
from packages.core.infrastructure.external.fx_service import FXService


async def _maybe_await(val):
    if inspect.isawaitable(val):
        return await val
    return val

class IntegrityError(Exception):
    """Raised when an operation would violate FIFO or financial integrity."""
    pass

class BlockingError(IntegrityError):
    """Raised when an operation is blocked to preserve data integrity."""
    pass

class InvestmentService:
    """
    Orchestrates investment tracking, including price updates and P/L calculations.
    """

    def __init__(self, repository, fx_service: Optional[FXService] = None):
        self.repository = repository
        self.fx_service = fx_service or FXService()

    async def add_investment(self, asset_type: str, ticker: str, quantity: Decimal,
                       buy_price: Decimal, buy_currency: str,
                       buy_date: Optional[datetime] = None) -> int:
        """
        Records a new investment holding.
        """
        quantity = Decimal(str(quantity)).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)
        buy_price = Decimal(str(buy_price))
        buy_date_dt = buy_date or datetime.now()

        # ── Calculate Buy Price in IDR (Persistence) ──
        buy_price_idr = buy_price
        if buy_currency.upper() == "USD":
            fx_buy = Decimal(str(self.fx_service.get_rate_at("USD/IDR", buy_date_dt.date())))
            buy_price_idr = (buy_price * fx_buy).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        investment = Investment(
            asset_type=asset_type,
            ticker=ticker,
            quantity=quantity,
            buy_price=buy_price,
            buy_currency=buy_currency.upper(),
            buy_price_idr=buy_price_idr,
            buy_date=buy_date_dt,
            status=InvestmentStatus.HOLDING,
            remaining_quantity=quantity,
        )
        return await _maybe_await(self.repository.save(investment))

    async def sell_investment(self, investment_id: int, quantity: Decimal,
                        sell_price: Decimal, sell_currency: str,
                        fees: Decimal = Decimal("0.0"), sell_date: Optional[datetime] = None,
                        record_profit_as_income: bool = False) -> Dict[str, Any]:
        """
        Processes a sell transaction and calculates realized P/L.
        Uses historical FX rates for both buy and sell dates for accurate financial reporting.

        Args:
            record_profit_as_income: When True, delegates to the atomic
                repository.sell_and_record_income() operation which records the
                realized gain as an income entry in a single transaction.
        """
        sell_and_record = getattr(self.repository, "sell_and_record_income", None)
        if not callable(sell_and_record):
            raise RuntimeError("Repository must implement the atomic sell_and_record_income operation")

        quantity = Decimal(str(quantity)).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)
        sell_price = Decimal(str(sell_price))
        sell_price = Decimal(str(sell_price))
        fees = Decimal(str(fees)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        investment = await _maybe_await(self.repository.get_by_id(investment_id))
        if not investment:
            raise ValueError(f"Investment with ID {investment_id} not found")

        # FIFO Integrity Check: Ensure we have enough in this specific lot
        remaining = investment.remaining_quantity
        if quantity > remaining:
            raise IntegrityError(
                f"Insufficient quantity in lot {investment_id} for {investment.ticker}. "
                f"Requested {quantity}, available {remaining}"
            )

        sell_date_dt = sell_date or datetime.now()
        buy_dt = investment.buy_date.date() if isinstance(investment.buy_date, datetime) else investment.buy_date
        sell_dt = sell_date_dt.date() if isinstance(sell_date_dt, datetime) else sell_date_dt

        # FX rates
        fx_buy = Decimal(str(self.fx_service.get_rate_at("USD/IDR", buy_dt)))
        fx_sell = Decimal(str(self.fx_service.get_rate_at("USD/IDR", sell_dt)))

        # Buy price in IDR
        if investment.buy_price_idr is not None:
            buy_price_idr = Decimal(str(investment.buy_price_idr))
        elif investment.buy_currency.upper() == "USD":
            buy_price_idr = (investment.buy_price * fx_buy).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            buy_price_idr = investment.buy_price

        # Sell price in IDR
        if sell_currency.upper() == "USD":
            sell_price_idr = (sell_price * fx_sell).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            sell_price_idr = sell_price

        # Realized P/L in IDR
        pl_idr = ((sell_price_idr - buy_price_idr) * quantity - fees).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Realized P/L Pct
        pl_pct = (((sell_price_idr - buy_price_idr) / buy_price_idr * 100) if buy_price_idr > 0 else Decimal("0")).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        calc_sell_price_usd = sell_price if sell_currency.upper() == "USD" else (sell_price / fx_sell).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        new_remaining = (remaining - quantity).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)
        status = InvestmentStatus.SOLD if new_remaining <= Decimal("0") else InvestmentStatus.PARTIAL_SOLD

        sell_tx = SellTransaction(
            sell_date=sell_date_dt,
            quantity=quantity,
            sell_price=sell_price,
            sell_currency=sell_currency,
            fees=fees,
            fx_rate=fx_sell,
            realized_pl=pl_idr,
            realized_pl_idr=pl_idr,
            realized_pl_pct=pl_pct,
            investment_id=investment_id,
            ticker=investment.ticker,
        )

        # ── Persistence: Always use atomic repository operation ──────────────
        income_data = {
            "date": sell_tx.sell_date,
            "amount": pl_idr,
            "source": f"Realized profit: {investment.ticker}",
            "income_type": "investment",
            "description": f"Realized profit from sale of {investment.ticker}",
        } if record_profit_as_income and pl_idr > 0 else None

        atomic_result = await _maybe_await(sell_and_record(
            sell_tx,
            income_data=income_data,
        ))
        income_id = atomic_result.get("income_id")

        return {
            "pl_idr": pl_idr,
            "pl_pct": pl_pct,
            "new_remaining": atomic_result.get("new_remaining", max(Decimal("0"), new_remaining)),
            "new_status": atomic_result.get("new_status", status.value),
            "sell_price_usd": calc_sell_price_usd,
            "fx_sell": fx_sell,
            "fx_buy": fx_buy,
            "ticker": investment.ticker,
            "sell_id": atomic_result.get("sell_id"),
            "income_id": income_id,
            "income_recorded": income_id is not None,
        }

    async def get_active_investments(self) -> List[Investment]:
        """
        Retrieves active investments enriched with current price and unrealized P/L.
        Implements a "Strict Value" protocol using live FX rates for USD assets.
        """
        investments = await _maybe_await(self.repository.get_all_active())
        fx_live = Decimal(str(self.fx_service.get_rate()))

        for inv in investments:
            # Get historical rate for buy date
            buy_dt = inv.buy_date.date() if isinstance(inv.buy_date, datetime) else inv.buy_date
            fx_buy = Decimal(str(self.fx_service.get_rate_at("USD/IDR", buy_dt)))

            # 1. Resolve/Calculate Buy Price in IDR
            if inv.buy_price_idr is None:
                if inv.buy_currency.upper() == "USD":
                    inv.buy_price_idr = (inv.buy_price * fx_buy).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                else:
                    inv.buy_price_idr = inv.buy_price

            # 2. Resolve Current Market Price (Strict Protocol)
            snapshot = await _maybe_await(self.repository.get_latest_snapshot(inv.id))
            current_price_idr = None
            current_price_usd = None
            price_date = None
            is_stale = False

            if snapshot:
                price_date = snapshot.get("snapshot_date") or snapshot.get("date")
                if snapshot.get("price_usd") is not None:
                    current_price_usd = Decimal(str(snapshot["price_usd"]))

                # Check for staleness (> 24h) safely across datetime, date, str
                if isinstance(price_date, datetime):
                    tz = getattr(price_date, 'tzinfo', None)
                    now = datetime.now(tz) if tz is not None else datetime.now()
                    is_stale = (now - price_date).total_seconds() > 86400
                elif isinstance(price_date, date):
                    is_stale = (datetime.now().date() - price_date).days > 1
                elif isinstance(price_date, str):
                    try:
                        dt_p = datetime.fromisoformat(price_date.replace(" ", "T"))
                        tz = getattr(dt_p, 'tzinfo', None)
                        now = datetime.now(tz) if tz is not None else datetime.now()
                        is_stale = (now - dt_p).total_seconds() > 86400
                    except Exception:
                        is_stale = False

                # Calculate Current Price in IDR using Market Price * LIVE FX (if USD based)
                if inv.buy_currency.upper() == "USD" and current_price_usd is not None:
                    current_price_idr = (current_price_usd * fx_live).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                elif snapshot.get("price_idr") is not None:
                    current_price_idr = Decimal(str(snapshot["price_idr"]))

            # 3. Calculate P/L Breakdown if current price exists
            if current_price_idr is not None:
                qty = inv.remaining_quantity if inv.remaining_quantity is not None else inv.quantity

                # Total P/L (IDR)
                inv.pl = ((current_price_idr - inv.buy_price_idr) * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                inv.pl_pct = (((current_price_idr - inv.buy_price_idr) / inv.buy_price_idr * 100) if inv.buy_price_idr > 0 else Decimal("0")).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                # Breakdown for USD-based assets
                if inv.buy_currency.upper() == "USD" and current_price_usd is not None:
                    # Capital Gain: Price growth at buy-date FX rate
                    inv.cap_gain = ((current_price_usd - inv.buy_price) * qty * fx_buy).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    # FX Gain: Impact of currency fluctuation on current USD value
                    inv.fx_gain = (current_price_usd * qty * (fx_live - fx_buy)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                else:
                    # For IDR assets, all gain is Capital Gain
                    inv.cap_gain = inv.pl
                    inv.fx_gain = Decimal("0.0")

                inv.current_price_idr = current_price_idr
                inv.current_price_date = price_date
                inv.is_stale = is_stale
                inv.fx_buy = fx_buy
                inv.fx_live = fx_live

        return investments

    async def toggle_favorite(self, investment_id: int) -> bool:
        """
        Toggles the favorite status of an investment.
        """
        return await _maybe_await(self.repository.toggle_favorite(investment_id))

    async def get_realized_pl_summary(self) -> List[SellTransaction]:
        """
        Retrieves all realized P/L transactions.
        """
        return await _maybe_await(self.repository.get_realized_pl())

    async def delete_investment(self, investment_id: int) -> bool:
        """
        Deletes an investment record after verifying FIFO integrity.
        """
        investment = await self.repository.get_by_id(investment_id)
        if not investment:
            return False

        # REQ-1: Block deletion if lot has dependencies (sells)
        if investment.status in [InvestmentStatus.PARTIAL_SOLD, InvestmentStatus.SOLD]:
            raise IntegrityError(f"Cannot delete investment {investment_id}: associated sales found.")

        # Recursive FIFO Integrity Check:
        lots = await self.repository.get_all_lots_by_ticker(investment.ticker)
        sells = await self.repository.get_all_sell_transactions_by_ticker(investment.ticker)

        total_buy_qty = sum(l.quantity for l in lots if l.id != investment_id)
        total_sell_qty = sum(s.quantity for s in sells)

        if total_buy_qty < total_sell_qty:
            raise IntegrityError(
                f"FIFO Violation: Deleting lot {investment_id} for {investment.ticker} would leave only "
                f"{total_buy_qty} units, which cannot cover {total_sell_qty} units already sold."
            )

        success = await self.repository.delete(investment_id)
        if not success and await self.repository.get_by_id(investment_id):
             raise IntegrityError(f"Atomic deletion failed for investment {investment_id}. Possible concurrent update.")
        return success

    async def prune_sold_lots(self) -> Dict[str, int]:
        """
        Remove fully-sold investment records from the database.
        """
        return await self.repository.prune_sold_lots()

    async def refresh_prices(self) -> Dict[str, Any]:
        """
        Fetches live prices for all active holdings and persists them.
        Returns a summary of updated tickers and any errors encountered.
        """
        from packages.core.infrastructure.external.yfinance_fetcher import YFinanceFetcher

        updated = []
        errors = []
        fx_rate = Decimal("16000.0") # Default fallback

        try:
            investments = await self.repository.get_all_active()
            try:
                from packages.core.infrastructure.external.fx_service import FXService
                fx_rate = Decimal(str(FXService().get_rate()))
            except Exception as fe:
                errors.append({"ticker": "SYSTEM", "error": f"FX Rate error: {fe}"})

            tickers = list({inv.ticker for inv in investments if inv.ticker})
            batch_data = YFinanceFetcher.fetch_batch_latest(tickers) if tickers else {}

            for inv in investments:
                if not inv.ticker:
                    continue

                try:
                    # 1. Fetch latest price using batch data, fallback to single fetch
                    data = batch_data.get(inv.ticker)
                    if not data:
                        data = YFinanceFetcher.fetch_latest_price(inv.ticker)
                    if not data:
                        raise ValueError(f"No price data returned for {inv.ticker}")

                    # 2. Calculate prices based on asset type and currency
                    raw_price = Decimal(str(data.price))
                    price_usd = raw_price
                    price_idr = Decimal("0.0")

                    # ── SPECIAL HANDLING: Asset Units & Currencies ──
                    from packages.core.utils.symbol_utils import SymbolFormatter
                    norm_ticker = SymbolFormatter.normalize(inv.ticker)

                    # A. Gold (Yahoo Futures GC=F / MGC=F are per Ounce)
                    is_gold = (
                        inv.asset_type.lower() == "gold" or
                        norm_ticker in ["GC=F", "MGC=F"] or
                        inv.ticker.upper() in ["XAU", "GOLD"]
                    )

                    if is_gold:
                        # Troy Ounce to Gram conversion factor.
                        # We use higher precision for USD price per gram to avoid rounding errors when converting to IDR
                        price_usd = (raw_price / Decimal("31.1034768")).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
                        price_idr = (price_usd * fx_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                    # B. IDX Stocks (Yahoo returns IDR instead of USD)
                    elif norm_ticker.endswith(".JK") or (data.metadata and ".JK" in data.metadata):
                        price_idr = raw_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        price_usd = (price_idr / fx_rate).quantize(Decimal('0.04'), rounding=ROUND_HALF_UP)

                    # C. Standard (USD based assets like US Stocks, Crypto, Forex)
                    else:
                        price_usd = raw_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        price_idr = (price_usd * fx_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                    # 3. Save snapshot
                    await self.repository.save_price_snapshot(inv.id, data.timestamp, price_usd, price_idr)
                    updated.append(inv.ticker)

                except Exception as e:
                    errors.append({"ticker": inv.ticker, "error": str(e)})
        except Exception as ge:
            errors.append({"ticker": "GLOBAL", "error": str(ge)})

        return {
            "updated": updated,
            "errors": errors,
            "fx_rate": float(fx_rate)
        }
