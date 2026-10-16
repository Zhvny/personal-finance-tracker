from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.application.investment_service import IntegrityError, InvestmentService
from packages.core.domain.models.investment import Investment, InvestmentStatus, SellTransaction


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    # Make all repo methods async by default
    repo.get_by_id = AsyncMock(return_value=None)
    repo.save = AsyncMock(return_value=1)
    repo.add_sell_transaction = AsyncMock(return_value=None)
    repo.update_status = AsyncMock(return_value=None)
    repo.delete = AsyncMock(return_value=True)
    repo.get_all_lots_by_ticker = AsyncMock(return_value=[])
    repo.get_all_sell_transactions_by_ticker = AsyncMock(return_value=[])
    repo.sell_and_record_income = AsyncMock(return_value={
        "sell_id": 1,
        "income_id": None,
        "new_remaining": Decimal("0"),
        "new_status": "sold",
    })
    return repo

@pytest.fixture
def mock_fx():
    fx = MagicMock()
    fx.get_rate.return_value = 16000.0
    fx.get_rate_at.return_value = 16000.0
    return fx

@pytest.fixture
def service(mock_repo, mock_fx):
    return InvestmentService(mock_repo, mock_fx)

def test_floating_point_drift_prevention():
    """Verify that using Decimal prevents common floating point errors like 0.1 + 0.2 != 0.3"""
    q1 = Decimal("0.1")
    q2 = Decimal("0.2")
    total = q1 + q2
    assert total == Decimal("0.3")
    assert total != Decimal("0.30000000000000004") # standard float error

@pytest.mark.asyncio
async def test_sell_integrity_insufficient_quantity(service, mock_repo):
    """Verify that selling more than available in a specific lot is blocked."""
    inv = Investment(
        id=1,
        asset_type="stock",
        ticker="AAPL",
        quantity=Decimal("10.0"),
        buy_price=Decimal("150.0"),
        buy_currency="USD",
        remaining_quantity=Decimal("10.0"),
        buy_date=datetime(2023, 1, 1)
    )
    mock_repo.get_by_id = AsyncMock(return_value=inv)

    with pytest.raises(IntegrityError) as excinfo:
        await service.sell_investment(1, Decimal("10.00000001"), Decimal("160.0"), "USD")

    assert "Insufficient quantity" in str(excinfo.value)

@pytest.mark.asyncio
async def test_delete_integrity_fifo_violation(service, mock_repo):
    """Verify that deleting a lot that would orphan existing sells is blocked."""
    inv1 = Investment(id=1, asset_type="stock", ticker="AAPL", quantity=Decimal("10.0"), buy_price=Decimal("100"), buy_currency="USD", buy_date=datetime(2023,1,1))
    inv2 = Investment(id=2, asset_type="stock", ticker="AAPL", quantity=Decimal("5.0"), buy_price=Decimal("110"), buy_currency="USD", buy_date=datetime(2023,2,1))

    sell = SellTransaction(quantity=Decimal("12.0"), sell_price=Decimal("150"), sell_date=datetime.now())

    mock_repo.get_by_id = AsyncMock(return_value=inv1)
    mock_repo.get_all_lots_by_ticker = AsyncMock(return_value=[inv1, inv2])
    mock_repo.get_all_sell_transactions_by_ticker = AsyncMock(return_value=[sell])

    with pytest.raises(IntegrityError) as excinfo:
        await service.delete_investment(1)

    assert "FIFO Violation" in str(excinfo.value)
    assert "would leave only 5.0 units, which cannot cover 12.0 units already sold" in str(excinfo.value)

@pytest.mark.asyncio
async def test_rounding_precision_idr(service, mock_repo, mock_fx):
    """Verify that money calculations are rounded to 2 decimal places (IDR standard)."""
    inv = Investment(
        id=1,
        asset_type="stock",
        ticker="AAPL",
        quantity=Decimal("1.0"),
        buy_price=Decimal("150.12345"),
        buy_currency="USD",
        remaining_quantity=Decimal("1.0"),
        buy_date=datetime(2023, 1, 1)
    )
    mock_repo.get_by_id = AsyncMock(return_value=inv)

    res = await service.sell_investment(1, Decimal("1.0"), Decimal("160.56789"), "USD")

    # Buy Price IDR: 150.12345 * 16000 = 2401975.20
    # Sell Price IDR: 160.56789 * 16000 = 2569086.24
    # Realized PL: 2569086.24 - 2401975.20 = 167111.04
    assert res['pl_idr'] == Decimal("167111.04")

@pytest.mark.asyncio
async def test_ghost_sell_simulation(service, mock_repo):
    """Specific simulation of the 'Ghost Sell' audit vector."""
    invA = Investment(id=1, asset_type="crypto", ticker="BTC", quantity=Decimal("10.0"), buy_price=Decimal("50000"), buy_currency="USD", buy_date=datetime(2024,1,1))
    invB = Investment(id=2, asset_type="crypto", ticker="BTC", quantity=Decimal("10.0"), buy_price=Decimal("55000"), buy_currency="USD", buy_date=datetime(2024,2,1))

    s1 = SellTransaction(quantity=Decimal("15.0"), sell_price=Decimal("60000"), sell_date=datetime.now())

    mock_repo.get_by_id = AsyncMock(return_value=invA)
    mock_repo.get_all_lots_by_ticker = AsyncMock(return_value=[invA, invB])
    mock_repo.get_all_sell_transactions_by_ticker = AsyncMock(return_value=[s1])

    with pytest.raises(IntegrityError) as excinfo:
        await service.delete_investment(1)

    assert "FIFO Violation" in str(excinfo.value)
    assert "cannot cover 15.0 units already sold" in str(excinfo.value)

@pytest.mark.asyncio
async def test_delete_investment_blocked_by_status(service, mock_repo):
    """Verify that deleting a lot with SOLD status is blocked."""
    inv = Investment(
        id=1,
        asset_type="stock",
        ticker="AAPL",
        quantity=Decimal("10.0"),
        buy_price=Decimal("100"),
        buy_currency="USD",
        status=InvestmentStatus.SOLD
    )
    mock_repo.get_by_id = AsyncMock(return_value=inv)

    with pytest.raises(IntegrityError, match="associated sales found"):
        await service.delete_investment(1)

@pytest.mark.asyncio
async def test_delete_investment_blocked_by_partial_status(service, mock_repo):
    """Verify that deleting a lot with PARTIAL_SOLD status is blocked."""
    inv = Investment(
        id=1,
        asset_type="stock",
        ticker="AAPL",
        quantity=Decimal("10.0"),
        buy_price=Decimal("100"),
        buy_currency="USD",
        status=InvestmentStatus.PARTIAL_SOLD,
        remaining_quantity=Decimal("5.0")
    )
    mock_repo.get_by_id = AsyncMock(return_value=inv)

    with pytest.raises(IntegrityError) as excinfo:
        await service.delete_investment(1)

    assert "associated sales found" in str(excinfo.value)
    assert "Cannot delete investment 1" in str(excinfo.value)
