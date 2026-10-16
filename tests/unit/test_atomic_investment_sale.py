from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.application.investment_service import InvestmentService
from packages.core.domain.models.investment import Investment


@pytest.mark.asyncio
async def test_profitable_sale_uses_atomic_repository_operation():
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=Investment(
        id=7,
        asset_type="stock",
        ticker="ALPHA",
        quantity=Decimal("10"),
        remaining_quantity=Decimal("10"),
        buy_price=Decimal("100"),
        buy_currency="IDR",
        buy_date=datetime(2025, 1, 1),
    ))
    repository.sell_and_record_income = AsyncMock(return_value={
        "sell_id": 9,
        "income_id": 11,
        "new_remaining": Decimal("8"),
        "new_status": "partial",
    })
    repository.add_sell_transaction = AsyncMock()
    repository.update_status = AsyncMock()
    fx_service = MagicMock()
    fx_service.get_rate_at.return_value = 1
    service = InvestmentService(repository, fx_service)

    result = await service.sell_investment(
        7, Decimal("2"), Decimal("150"), "IDR",
        sell_date=datetime(2025, 2, 1), record_profit_as_income=True,
    )

    repository.sell_and_record_income.assert_awaited_once()
    repository.add_sell_transaction.assert_not_awaited()
    repository.update_status.assert_not_awaited()
    assert result["income_recorded"] is True
    assert result["new_remaining"] == Decimal("8")


@pytest.mark.asyncio
async def test_atomic_sale_failure_does_not_fall_back_to_partial_writes():
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=Investment(
        id=7,
        asset_type="stock",
        ticker="ALPHA",
        quantity=Decimal("10"),
        remaining_quantity=Decimal("10"),
        buy_price=Decimal("100"),
        buy_currency="IDR",
        buy_date=datetime(2025, 1, 1),
    ))
    repository.sell_and_record_income = AsyncMock(side_effect=RuntimeError("income insert failed"))
    repository.add_sell_transaction = AsyncMock()
    repository.update_status = AsyncMock()
    fx_service = MagicMock()
    fx_service.get_rate_at.return_value = 1
    service = InvestmentService(repository, fx_service)

    with pytest.raises(RuntimeError, match="income insert failed"):
        await service.sell_investment(
            7, Decimal("2"), Decimal("150"), "IDR",
            sell_date=datetime(2025, 2, 1), record_profit_as_income=True,
        )

    repository.add_sell_transaction.assert_not_awaited()
    repository.update_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_sale_without_derived_income_still_uses_atomic_repository_operation():
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=Investment(
        id=7,
        asset_type="stock",
        ticker="ALPHA",
        quantity=Decimal("10"),
        remaining_quantity=Decimal("10"),
        buy_price=Decimal("100"),
        buy_currency="IDR",
        buy_date=datetime(2025, 1, 1),
    ))
    repository.sell_and_record_income = AsyncMock(return_value={
        "sell_id": 9,
        "income_id": None,
        "new_remaining": Decimal("8"),
        "new_status": "partial",
    })
    repository.add_sell_transaction = AsyncMock()
    repository.update_status = AsyncMock()
    fx_service = MagicMock()
    fx_service.get_rate_at.return_value = 1
    service = InvestmentService(repository, fx_service)

    result = await service.sell_investment(
        7, Decimal("2"), Decimal("150"), "IDR",
        sell_date=datetime(2025, 2, 1), record_profit_as_income=False,
    )

    repository.sell_and_record_income.assert_awaited_once()
    assert repository.sell_and_record_income.await_args.kwargs["income_data"] is None
    repository.add_sell_transaction.assert_not_awaited()
    repository.update_status.assert_not_awaited()
    assert result["income_recorded"] is False
