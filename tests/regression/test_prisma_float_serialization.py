"""
Money precision on Prisma write paths (Decimal, not float).

HISTORY
-------
Prisma schema used to type money/quantity columns as `Float` while Postgres
stores DECIMAL. Repositories coerced Decimal -> float, silently losing cents.
Schema now types per-profile financial models (Expense, Income, Investment,
SellTransaction, HistoricalPrice, Budget) as `Decimal`, and repositories must
hand Prisma a `Decimal` (never float) so Decimal("123.45") round-trips exactly.

Business-domain models (BusinessProject, DailyProgressLog, LaborAttendanceLog,
ProjectMilestone) are still `Float` in Prisma — those tests below still assert
float coercion and are unchanged.

Mocks: no live Postgres/Prisma engine needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_prisma_capture(model_attr: str, method: str = "create") -> tuple[MagicMock, dict]:
    """Return (mock_db, captured) where captured['data'] holds the payload
    passed to ``db.<model_attr>.<method>(data=...)``. The mocked create/upsert
    returns an object with ``id=1``."""
    captured: Dict[str, Any] = {}

    async def _fake(*args, **kwargs):
        captured["data"] = kwargs.get("data")
        return MagicMock(id=1)

    mock_db = MagicMock()
    setattr(getattr(mock_db, model_attr), method, AsyncMock(side_effect=_fake))
    return mock_db, captured


def _assert_floats(data: dict, fields: list[str]) -> None:
    """Assert each named field is a real float (not Decimal, not str)."""
    for f in fields:
        assert f in data, f"expected field {f!r} in Prisma payload"
        val = data[f]
        assert isinstance(val, float), (
            f"field {f!r} must be float for Prisma Float schema, "
            f"got {type(val).__name__}={val!r}"
        )
        # Guard the specific regression: a Decimal or a stringified number.
        assert not isinstance(val, Decimal), f"field {f!r} leaked a Decimal"


def _assert_decimals(data: dict, fields: list[str]) -> None:
    """Assert each named field is a Decimal (never float — float loses cents)."""
    for f in fields:
        assert f in data, f"expected field {f!r} in Prisma payload"
        val = data[f]
        assert isinstance(val, Decimal), (
            f"field {f!r} must be Decimal for Prisma Decimal schema, "
            f"got {type(val).__name__}={val!r}"
        )
        assert not isinstance(val, float), f"field {f!r} leaked a float"


# ---------------------------------------------------------------------------
# Investment.save  -> investment.create
# ---------------------------------------------------------------------------

async def test_investment_save_preserves_decimal():
    from packages.core.domain.models import Investment, InvestmentStatus
    from packages.core.infrastructure.persistence import postgres_investment_repository as mod

    inv = Investment(
        asset_type="stock",
        ticker="BBRI",
        quantity=Decimal("10.5"),
        buy_price=Decimal("100.25"),
        buy_currency="IDR",
        buy_price_idr=Decimal("100.25"),
        buy_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        status=InvestmentStatus.HOLDING,
        remaining_quantity=Decimal("10.5"),
    )
    mock_db, captured = _mock_prisma_capture("investment")
    with patch.object(mod, "_db", AsyncMock(return_value=mock_db)):
        await mod.PostgresInvestmentRepository().save(inv)

    data = captured["data"]
    _assert_decimals(data, ["quantity", "buy_price", "buy_price_idr", "remaining_quantity"])
    assert data["quantity"] == Decimal("10.5")
    assert data["buy_price"] == Decimal("100.25")


# ---------------------------------------------------------------------------
# add_sell_transaction -> selltransaction.create
# ---------------------------------------------------------------------------

async def test_add_sell_transaction_preserves_decimal():
    from packages.core.domain.models import SellTransaction
    from packages.core.infrastructure.persistence import postgres_investment_repository as mod

    sell = SellTransaction(
        investment_id=1,
        ticker="BBRI",
        sell_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        quantity=Decimal("4"),
        sell_price=Decimal("150.00"),
        sell_currency="USD",
        fees=Decimal("1.5"),
        fx_rate=Decimal("16000"),
        realized_pl=Decimal("1000"),
        realized_pl_idr=Decimal("1000"),
        realized_pl_pct=Decimal("37.5"),
    )
    mock_db, captured = _mock_prisma_capture("selltransaction")
    with patch.object(mod, "_db", AsyncMock(return_value=mock_db)):
        await mod.PostgresInvestmentRepository().add_sell_transaction(sell)

    _assert_decimals(
        captured["data"],
        ["quantity", "sell_price_usd", "fees", "realized_pl_idr", "realized_pl_pct"],
    )


# ---------------------------------------------------------------------------
# Expense.save -> expense.create (also enum serialization)
# ---------------------------------------------------------------------------

async def test_expense_save_preserves_decimal_and_serialises_enums():
    from packages.core.domain.models import Expense
    from packages.core.infrastructure.persistence import postgres_expense_repository as mod

    exp = Expense(
        amount=Decimal("12345.67"),
        description="regression",
        category="food",
        payment_method="cash",
        date=datetime(2025, 3, 1, tzinfo=timezone.utc),
    )
    mock_db, captured = _mock_prisma_capture("expense")
    with patch.object(mod, "_db", AsyncMock(return_value=mock_db)):
        await mod.PostgresExpenseRepository().save(exp)

    data = captured["data"]
    _assert_decimals(data, ["amount"])
    # Enums must be plain strings, not raw Python enum objects.
    assert isinstance(data["category"], str), f"category not str: {type(data['category'])}"
    assert isinstance(data["payment_method"], str), f"payment_method not str: {type(data['payment_method'])}"


async def test_expense_decimal_round_trip_preserves_123_45():
    """Decimal("123.45") reaches Prisma bit-exact — the cents-loss regression."""
    from packages.core.domain.models import Expense
    from packages.core.infrastructure.persistence import postgres_expense_repository as mod

    exp = Expense(
        amount=Decimal("123.45"),
        description="round-trip",
        category="food",
        payment_method="cash",
        date=datetime(2025, 3, 1, tzinfo=timezone.utc),
    )
    mock_db, captured = _mock_prisma_capture("expense")
    with patch.object(mod, "_db", AsyncMock(return_value=mock_db)):
        await mod.PostgresExpenseRepository().save(exp)

    assert captured["data"]["amount"] == Decimal("123.45")
    assert isinstance(captured["data"]["amount"], Decimal)


# ---------------------------------------------------------------------------
# Income.save -> income.create (amount is the only Float field)
# ---------------------------------------------------------------------------

async def test_income_save_preserves_decimal_amount():
    from packages.core.domain.models import Income
    from packages.core.infrastructure.persistence import postgres_income_repository as mod

    inc = Income(
        amount=Decimal("2500000.50"),
        source="salary",
        income_type="salary",
        date=datetime(2025, 4, 1, tzinfo=timezone.utc),
    )
    mock_db, captured = _mock_prisma_capture("income")
    with patch.object(mod, "_db", AsyncMock(return_value=mock_db)):
        await mod.PostgresIncomeRepository().save(inc)

    _assert_decimals(captured["data"], ["amount"])
    assert captured["data"]["amount"] == Decimal("2500000.50")
    assert isinstance(captured["data"]["income_type"], str)



# ---------------------------------------------------------------------------
# BusinessAnalyticsService — guard the 5 Prisma write sites.
#
# These methods already wrap numerics in float(); this locks that in even when
# a caller passes Decimal (e.g. from a Pydantic model or DB read). The service
# uses `_db_module.get_db()`, so we patch that symbol on the service module.
# ---------------------------------------------------------------------------


def _patch_analytics_db(mod, mock_db):
    """Patch the get_db accessor used by business_analytics_service."""
    fake_module = MagicMock()
    fake_module.get_db = AsyncMock(return_value=mock_db)
    return patch.object(mod, "_db_module", fake_module)


async def test_business_project_create_coerces_budget_to_float():
    from packages.core.application import business_analytics_service as mod

    mock_db, captured = _mock_prisma_capture("businessproject")
    svc = mod.BusinessAnalyticsService()
    with _patch_analytics_db(mod, mock_db):
        await svc.create_project(
            name="Tower A",
            code="twr-a",
            budget=Decimal("1000000.50"),
            start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )
    _assert_floats(captured["data"], ["budget"])


async def test_daily_progress_upsert_coerces_floats():
    from packages.core.application import business_analytics_service as mod

    captured: Dict[str, Any] = {}

    async def _fake_upsert(*args, **kwargs):
        captured["data"] = kwargs.get("data")
        return MagicMock(id=1)

    mock_db = MagicMock()
    mock_db.dailyprogresslog.upsert = AsyncMock(side_effect=_fake_upsert)

    svc = mod.BusinessAnalyticsService()
    with _patch_analytics_db(mod, mock_db):
        await svc.record_daily_progress(
            project_id=1,
            log_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
            planned_pct=Decimal("12.5"),
            actual_pct=Decimal("10.0"),
            actual_cost=Decimal("500000.75"),
            headcount=3,
            work_hours=Decimal("7.5"),
        )
    # upsert nests the payload under create/update — both must be coerced.
    for branch in ("create", "update"):
        _assert_floats(
            captured["data"][branch],
            ["plannedProgressFloat", "actualProgressFloat", "actualCost", "workHours"],
        )


async def test_labor_attendance_create_coerces_man_hours():
    from packages.core.application import business_analytics_service as mod

    mock_db, captured = _mock_prisma_capture("laborattendancelog")
    svc = mod.BusinessAnalyticsService()
    with _patch_analytics_db(mod, mock_db):
        await svc.record_labor_attendance(
            project_id=1,
            log_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
            worker_role="mason",
            present_count=8,
            total_count=10,
            man_hours=Decimal("64.0"),
        )
    _assert_floats(captured["data"], ["manHours"])


async def test_milestone_create_coerces_weight():
    from packages.core.application import business_analytics_service as mod

    mock_db, captured = _mock_prisma_capture("projectmilestone")
    svc = mod.BusinessAnalyticsService()
    with _patch_analytics_db(mod, mock_db):
        await svc.add_milestone(
            project_id=1,
            title="Foundation",
            target_date=datetime(2025, 4, 1, tzinfo=timezone.utc),
            weight=Decimal("2.5"),
        )
    _assert_floats(captured["data"], ["weight"])
