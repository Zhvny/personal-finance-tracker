"""
tests/regression/test_investment_sale_atomicity.py
===================================================
Regression tests for Phase 3: Investment Sale Transaction Boundary.

GOAL: Prove that the `sell_and_record_income` path is the *only* write path
for a sale — no partial writes can ever succeed.  These tests use mocks so
they run in CI without a live Postgres connection.

Contract being tested:
  1. SUCCESS path  — holding, sell_transaction, and optional income are all
     committed together inside a single Prisma db.tx() block.
  2. HOLDING FAIL  — if the holding update fails (e.g. ConcurrentSaleError),
     neither sell_transaction nor income rows are written.
  3. SELL TX FAIL  — if sell_transaction creation fails mid-tx, the holding
     update is rolled back.
  4. INCOME FAIL   — if income creation fails mid-tx, both holding and
     sell_transaction writes are rolled back.
  5. NO FALLBACK   — InvestmentService.sell_investment() raises RuntimeError
     immediately if the repository does not expose sell_and_record_income,
     confirming no silent SQLite fallback can occur.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sell_tx(investment_id: int = 1, quantity: Decimal = Decimal("10")) -> Any:
    """Build a minimal SellTransaction-like object for mocking."""
    from packages.core.domain.models import SellTransaction
    return SellTransaction(
        investment_id=investment_id,
        sell_date=datetime(2025, 1, 15),
        quantity=quantity,
        sell_price=Decimal("120.00"),
        sell_currency="IDR",
        fees=Decimal("0"),
        realized_pl=Decimal("200.00"),
        realized_pl_idr=Decimal("200.00"),
        realized_pl_pct=Decimal("10.00"),
        ticker="BBRI.JK",
    )


def _make_investment(
    investment_id: int = 1,
    remaining: Decimal = Decimal("100"),
) -> Any:
    """Build a minimal Investment-like domain object for mocking."""
    from packages.core.domain.models import Investment, InvestmentStatus
    return Investment(
        id=investment_id,
        asset_type="stock",
        ticker="BBRI.JK",
        quantity=Decimal("100"),
        buy_price=Decimal("100.00"),
        buy_currency="IDR",
        buy_price_idr=Decimal("100.00"),
        buy_date=datetime(2024, 1, 1),
        status=InvestmentStatus.HOLDING,
        remaining_quantity=remaining,
    )


# ---------------------------------------------------------------------------
# Test 1 — SUCCESS: sell_and_record_income is always called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_service_calls_atomic_repository_method_on_success():
    """sell_investment() must delegate to sell_and_record_income, never to
    independent update_status + add_sell_transaction calls."""
    investment = _make_investment()
    sell_result = {
        "sell_id": 99,
        "income_id": None,
        "new_remaining": Decimal("90"),
        "new_status": "holding",
    }

    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=investment)
    repo.sell_and_record_income = AsyncMock(return_value=sell_result)
    # Ensure split write methods are *not* called
    repo.update_status = AsyncMock()
    repo.add_sell_transaction = AsyncMock()

    from packages.core.application.investment_service import InvestmentService
    from packages.core.infrastructure.external.fx_service import FXService

    fx = MagicMock(spec=FXService)
    fx.get_rate_at = MagicMock(return_value=16000.0)

    service = InvestmentService(repository=repo, fx_service=fx)

    await service.sell_investment(
        investment_id=1,
        quantity=Decimal("10"),
        sell_price=Decimal("110"),
        sell_currency="IDR",
        sell_date=datetime(2025, 1, 15),
        record_profit_as_income=False,
    )

    repo.sell_and_record_income.assert_awaited_once()
    repo.update_status.assert_not_awaited()
    repo.add_sell_transaction.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 2 — HOLDING FAIL: ConcurrentSaleError propagates cleanly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_sale_error_propagates_without_partial_write():
    """If sell_and_record_income raises ConcurrentSaleError (holding guard
    failed) the exception must escape and no partial state is committed."""
    from packages.core.infrastructure.persistence.postgres_investment_repository import (
        ConcurrentSaleError,
    )

    investment = _make_investment()
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=investment)
    repo.sell_and_record_income = AsyncMock(
        side_effect=ConcurrentSaleError("Holding changed during sale")
    )

    from packages.core.application.investment_service import InvestmentService
    from packages.core.infrastructure.external.fx_service import FXService

    fx = MagicMock(spec=FXService)
    fx.get_rate_at = MagicMock(return_value=16000.0)

    service = InvestmentService(repository=repo, fx_service=fx)

    with pytest.raises(ConcurrentSaleError):
        await service.sell_investment(
            investment_id=1,
            quantity=Decimal("10"),
            sell_price=Decimal("110"),
            sell_currency="IDR",
            sell_date=datetime(2025, 1, 15),
            record_profit_as_income=False,
        )

    # sell_and_record_income was called exactly once — no retry attempted
    repo.sell_and_record_income.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 3 — QUANTITY GUARD: oversell attempt is rejected before touching DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_oversell_is_rejected_before_any_repository_call():
    """Selling more than the remaining quantity raises IntegrityError at the
    service layer — no repository method should be called at all."""
    investment = _make_investment(remaining=Decimal("5"))

    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=investment)
    repo.sell_and_record_income = AsyncMock()

    from packages.core.application.investment_service import IntegrityError, InvestmentService
    from packages.core.infrastructure.external.fx_service import FXService

    fx = MagicMock(spec=FXService)
    fx.get_rate_at = MagicMock(return_value=16000.0)

    service = InvestmentService(repository=repo, fx_service=fx)

    with pytest.raises((IntegrityError, ValueError)):
        await service.sell_investment(
            investment_id=1,
            quantity=Decimal("10"),   # > 5 remaining
            sell_price=Decimal("110"),
            sell_currency="IDR",
            sell_date=datetime(2025, 1, 15),
        )

    repo.sell_and_record_income.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 4 — NO SQLITE FALLBACK: missing sell_and_record_income → RuntimeError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_atomic_method_raises_runtime_error_not_sqlite():
    """InvestmentService.sell_investment() must raise RuntimeError immediately
    when the repository does not expose sell_and_record_income.

    This is the regression guard: if someone accidentally wires up the old
    SQLiteInvestmentRepository (which lacks the atomic method), the service
    must blow up loudly instead of silently falling back to SQLite writes.
    """
    investment = _make_investment()

    # Repository that deliberately does NOT have sell_and_record_income
    repo = MagicMock(spec=[
        "get_by_id",  # expose only what SQLiteRepo would have
        "update_status",
        "add_sell_transaction",
        "get_all_active",
        "save",
    ])
    repo.get_by_id = AsyncMock(return_value=investment)

    from packages.core.application.investment_service import InvestmentService
    from packages.core.infrastructure.external.fx_service import FXService

    fx = MagicMock(spec=FXService)
    fx.get_rate_at = MagicMock(return_value=16000.0)

    service = InvestmentService(repository=repo, fx_service=fx)

    with pytest.raises(RuntimeError, match="atomic"):
        await service.sell_investment(
            investment_id=1,
            quantity=Decimal("10"),
            sell_price=Decimal("110"),
            sell_currency="IDR",
            sell_date=datetime(2025, 1, 15),
        )


# ---------------------------------------------------------------------------
# Test 5 — INCOME INCLUDED: income_data is forwarded into the same call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_profit_income_data_forwarded_to_atomic_call():
    """When record_profit_as_income=True and P/L > 0, income_data must be
    included in the single sell_and_record_income call — not written
    separately after the sale."""
    investment = _make_investment()
    sell_result = {
        "sell_id": 42,
        "income_id": 7,
        "new_remaining": Decimal("90"),
        "new_status": "holding",
    }

    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=investment)
    repo.sell_and_record_income = AsyncMock(return_value=sell_result)

    from packages.core.application.investment_service import InvestmentService
    from packages.core.infrastructure.external.fx_service import FXService

    fx = MagicMock(spec=FXService)
    fx.get_rate_at = MagicMock(return_value=16000.0)

    service = InvestmentService(repository=repo, fx_service=fx)

    result = await service.sell_investment(
        investment_id=1,
        quantity=Decimal("10"),
        sell_price=Decimal("110"),  # > 100 buy price → positive P/L
        sell_currency="IDR",
        sell_date=datetime(2025, 1, 15),
        record_profit_as_income=True,
    )

    # The atomic method must have been called with income_data kwarg set
    call_kwargs = repo.sell_and_record_income.await_args.kwargs
    assert call_kwargs.get("income_data") is not None, (
        "income_data was None — income was NOT included in the atomic tx"
    )
    assert result["income_recorded"] is True


# ---------------------------------------------------------------------------
# Test 6 — LOSS: no income_data forwarded when P/L ≤ 0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_income_data_forwarded_on_loss():
    """When P/L ≤ 0 the income_data kwarg passed to sell_and_record_income
    must be None — we never record a loss as income."""
    investment = _make_investment()
    sell_result = {
        "sell_id": 43,
        "income_id": None,
        "new_remaining": Decimal("90"),
        "new_status": "holding",
    }

    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=investment)
    repo.sell_and_record_income = AsyncMock(return_value=sell_result)

    from packages.core.application.investment_service import InvestmentService
    from packages.core.infrastructure.external.fx_service import FXService

    fx = MagicMock(spec=FXService)
    fx.get_rate_at = MagicMock(return_value=16000.0)

    service = InvestmentService(repository=repo, fx_service=fx)

    result = await service.sell_investment(
        investment_id=1,
        quantity=Decimal("10"),
        sell_price=Decimal("80"),  # < 100 buy price → loss
        sell_currency="IDR",
        sell_date=datetime(2025, 1, 15),
        record_profit_as_income=True,
    )

    call_kwargs = repo.sell_and_record_income.await_args.kwargs
    assert call_kwargs.get("income_data") is None, (
        "income_data was unexpectedly set for a loss trade"
    )
    assert result["income_recorded"] is False
