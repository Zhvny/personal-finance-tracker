import logging
from datetime import datetime, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from packages.api.backend.routers.deps import (
    _bust_behavioral_cache,
    _inv_repo,
    get_live_fx_rate,
    income_service,
    investment_service,
)
from packages.api.backend.security.core import require_scope
from packages.core.application.investment_service import IntegrityError

logger = logging.getLogger("backend.investments")

router = APIRouter(dependencies=[Depends(require_scope("write"))])

# ═════════════════════════════════════════════════════════════════════
# INVESTMENTS
# ═════════════════════════════════════════════════════════════════════


class InvestmentIn(BaseModel):
    asset_type: str
    ticker: str
    quantity: float
    buy_price: float
    buy_currency: str = "IDR"
    buy_date: str

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Quantity must be greater than 0")
        return v

    @field_validator("buy_price")
    @classmethod
    def buy_price_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Buy price must be greater than 0")
        return v


class SellIn(BaseModel):
    quantity: float
    sell_price: float
    sell_currency: str = "IDR"
    sell_date: str
    fees: float = 0.0


@router.get("/api/investments")
async def list_investments():
    logger.info("Fetching active investments...")
    try:
        # Use the service which handles enrichment/active logic
        results = await investment_service.get_active_investments()
        logger.info(f"Successfully fetched {len(results)} investments")
        return results
    except Exception:
        # Log full traceback server-side; never expose internals to the client.
        logger.exception("Error in list_investments")
        raise HTTPException(status_code=500, detail="Could not fetch investments. Check server logs for details.")


@router.post("/api/investments")
async def add_investment(body: InvestmentIn):
    dt = datetime.fromisoformat(body.buy_date)
    new_id = await investment_service.add_investment(
        asset_type=body.asset_type,
        ticker=body.ticker.upper(),
        quantity=body.quantity,
        buy_price=body.buy_price,
        buy_currency=body.buy_currency,
        buy_date=dt,
    )
    _bust_behavioral_cache()
    return {"id": new_id, "ok": True}


@router.post("/api/investments/{inv_id}/sell")
async def sell_investment(inv_id: int, body: SellIn):
    dt = datetime.fromisoformat(body.sell_date)
    try:
        result = await investment_service.sell_investment(
            investment_id=inv_id,
            quantity=body.quantity,
            sell_price=body.sell_price,
            sell_currency=body.sell_currency,
            fees=body.fees,
            sell_date=dt,
            record_profit_as_income=True,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        logger.exception("Atomic investment sale failed")
        raise HTTPException(503, "Investment sale could not be recorded; no changes were committed.")

    if result["income_recorded"]:
        try:
            await income_service.apply_post_record_side_effects(
                amount=result["pl_idr"],
                source=f"Profit from selling {body.quantity} {result['ticker']}",
                income_type="investment",
                description="Realized profit (automated from sell)",
                apply_allocation=True,
            )
        except Exception:
            # The sale and income are already committed together. Preserve that
            # result even if an optional notification/reward integration fails.
            logger.exception("Post-income sale side effects failed")

    _bust_behavioral_cache()
    return {
        "ok": True,
        "realized_pl": result["pl_idr"],
        "realized_pl_pct": result["pl_pct"],
        "new_remaining": result["new_remaining"],
        "new_status": result["new_status"],
        "income_recorded": result["income_recorded"],
        "income_error": None,
    }


@router.delete("/api/investments/{inv_id}")
async def delete_investment(inv_id: int):
    if inv_id <= 0:
        raise HTTPException(400, "Invalid investment ID")
    try:
        success = await investment_service.delete_investment(inv_id)
        if not success:
            raise HTTPException(404, "Investment not found")
        _bust_behavioral_cache()
        return {"ok": True}
    except IntegrityError as e:
        raise HTTPException(400, str(e))


@router.post("/api/investments/{inv_id}/favorite")
async def toggle_favorite(inv_id: int):
    success = await investment_service.toggle_favorite(inv_id)
    return {"ok": success}


@router.post("/api/investments/prune")
async def prune_portfolio():
    """
    Remove fully-sold investment rows and their historical snapshots.
    """
    result = await investment_service.prune_sold_lots()
    return result


@router.get("/api/investments/realized")
async def get_realized_pl():
    sells = await _inv_repo.get_realized_pl()
    if not sells:
        return {"transactions": [], "summary": {"total_pl": 0, "wins": 0, "losses": 0, "win_rate": 0}}

    total_pl = sum(s.realized_pl for s in sells)
    wins = sum(1 for s in sells if s.realized_pl > 0)
    losses = sum(1 for s in sells if s.realized_pl < 0)

    # Map back to dict for JSON
    transactions = []
    for s in sells:
        transactions.append(
            {
                "id": s.id,
                "investment_id": s.investment_id,
                "ticker": s.ticker,
                "sell_date": s.sell_date.isoformat(),
                "quantity": s.quantity,
                "sell_price": s.sell_price,
                "sell_price_usd": s.sell_price,
                "sell_currency": s.sell_currency,
                "fees": s.fees,
                "realized_pl_idr": s.realized_pl,
                "realized_pl_pct": s.realized_pl_pct,
            }
        )

    return {
        "transactions": transactions,
        "summary": {
            "total_pl": total_pl,
            "wins": wins,
            "losses": losses,
            "win_rate": wins / len(sells) * 100 if sells else 0,
        },
    }


@router.get("/api/investments/{inv_id}/history")
async def get_investment_history(inv_id: int):
    """
    Returns price history for a specific investment lot.
    Surgically fetches data from buy_date to today for accurate performance tracking.
    """
    # 1. Fetch lot details to get buy_date and ticker
    inv = await _inv_repo.get_by_id(inv_id)
    if not inv:
        raise HTTPException(404, "Investment lot not found")

    # 2. Define range: buy_date to today (inclusive)
    # We use tomorrow as end_date because yfinance 'end' is exclusive.
    start_dt = inv.buy_date
    end_dt = datetime.now() + timedelta(days=1)

    try:
        from packages.core.infrastructure.external.yfinance_fetcher import YFinanceFetcher

        # 3. Fetch from market (yfinance)
        market_df = YFinanceFetcher.fetch_history(inv.ticker, start_dt, end_dt)

        if market_df.empty:
            # Fallback to local snapshots if market data is unavailable (e.g. invalid ticker)
            return await _inv_repo.get_all_snapshots(inv_id)

        # Get current FX rate for IDR conversion
        # (Ideally we'd use historical FX, but current is a close enough proxy for trend visualization)
        fx = get_live_fx_rate()
        history = []

        for dt, row in market_df.iterrows():
            close = float(row["Close"])
            if pd.isna(close):
                continue

            # ── Unit/Currency Handling ──
            p_usd, p_idr = close, close * fx

            if inv.asset_type == "gold":
                # Convert $/oz to $/gram
                p_usd = close / 31.1034768
                p_idr = p_usd * fx
            elif inv.ticker.upper().endswith(".JK"):
                # yfinance returns IDR for .JK
                p_idr = close
                p_usd = p_idr / fx

            history.append(
                {"snapshot_date": dt.date().isoformat(), "price_usd": p_usd, "price_idr": p_idr, "is_market_data": True}
            )

        return history
    except Exception as e:
        import logging

        logging.error(f"Error augmenting history for {inv.ticker}: {e}")
        # Final fallback to system snapshots
        return await _inv_repo.get_all_snapshots(inv_id)


@router.post("/api/investments/refresh-prices")
async def refresh_investment_prices():
    """
    Fetch live prices for all active holdings and persist them.
    """
    try:
        result = await investment_service.refresh_prices()
        investments = await investment_service.get_active_investments()

        return {
            "updated": result["updated"],
            "errors": result["errors"],
            "investments": investments,
            "fx_rate": result["fx_rate"],
        }
    except Exception as e:
        logger.exception("refresh_investment_prices failed")
        fx_fallback = False
        try:
            investments = await investment_service.get_active_investments()
        except Exception:
            logger.exception("refresh_investment_prices fallback fetch failed")
            investments = []

        try:
            fx_rate = float(await get_live_fx_rate())
        except Exception:
            logger.exception("refresh_investment_prices FX fallback failed")
            fx_rate = 16000.0
            fx_fallback = True

        return {
            "updated": [],
            "errors": [{"ticker": "SERVER", "error": str(e)}],
            "investments": investments,
            "fx_rate": fx_rate,
            "fx_rate_stale": fx_fallback,
        }
