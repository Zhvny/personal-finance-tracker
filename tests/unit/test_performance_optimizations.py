from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.api.backend.routers.deps import _get_crypto_from_portfolio
from packages.core.application.investment_service import InvestmentService
from packages.core.domain.models.investment import Investment, InvestmentStatus
from packages.core.domain.models.market_data import MarketData
from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager


@pytest.fixture
def mock_investment_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_fx_service():
    fx = MagicMock()
    fx.get_rate.return_value = 15000.0
    return fx


@pytest.mark.asyncio
async def test_batch_price_fetching_in_refresh_prices(mock_investment_repo, mock_fx_service):
    service = InvestmentService(repository=mock_investment_repo, fx_service=mock_fx_service)

    # Mock active investments
    inv1 = Investment(
        id=1,
        asset_type="crypto",
        ticker="BTC-USD",
        quantity=Decimal("1.0"),
        buy_price=Decimal("50000.0"),
        buy_currency="USD",
        buy_price_idr=Decimal("750000000.0"),
        buy_date=datetime.now(),
        status=InvestmentStatus.HOLDING,
        remaining_quantity=Decimal("1.0"),
    )
    inv2 = Investment(
        id=2,
        asset_type="stock",
        ticker="AAPL",
        quantity=Decimal("10.0"),
        buy_price=Decimal("150.0"),
        buy_currency="USD",
        buy_price_idr=Decimal("22500000.0"),
        buy_date=datetime.now(),
        status=InvestmentStatus.HOLDING,
        remaining_quantity=Decimal("10.0"),
    )
    mock_investment_repo.get_all_active.return_value = [inv1, inv2]

    with (
        patch(
            "packages.core.infrastructure.external.yfinance_fetcher.YFinanceFetcher.fetch_batch_latest"
        ) as mock_batch,
        patch(
            "packages.core.infrastructure.external.yfinance_fetcher.YFinanceFetcher.fetch_latest_price"
        ) as mock_single,
    ):
        # Batch returns data for BTC but misses AAPL
        mock_batch.return_value = {
            "BTC-USD": MarketData(ticker="BTC-USD", price=60000.0, timestamp=datetime.now(), metadata="")
        }
        mock_single.return_value = MarketData(ticker="AAPL", price=160.0, timestamp=datetime.now(), metadata="")

        result = await service.refresh_prices()

        assert "BTC-USD" in result["updated"]
        assert "AAPL" in result["updated"]
        mock_batch.assert_called_once()
        mock_single.assert_called_once_with("AAPL")


from contextlib import contextmanager


@pytest.mark.xfail(reason="Pre-existing: requires connection pool mock; tracked separately (tracking: fix mock-scope)")
def test_database_manager_execute_rollback():
    """Test that execute rolls back on error to avoid breaking the connection pool."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = Exception("DB Error")
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    @contextmanager
    def mock_get_conn(schema=None):
        yield mock_conn

    with patch.object(DatabaseManager, "get_connection", side_effect=mock_get_conn):
        with pytest.raises(Exception, match="DB Error"):
            DatabaseManager.execute("INSERT INTO test_tbl (id) VALUES (1)")

        mock_conn.rollback.assert_called_once()


@pytest.mark.xfail(
    reason="Pre-existing: requires real DB; mock setup not compatible with pytest-asyncio auto mode (tracking: fix mock-scope)"
)
@patch("packages.api.backend.routers.deps.Database.query")
@patch("packages.api.backend.routers.deps.os.path.exists", return_value=True)
def test_get_crypto_from_portfolio_no_n1(mock_exists, mock_db_query):
    """Test that _get_crypto_from_portfolio uses JOIN and handles data correctly."""
    mock_db_query.return_value = [
        {"remaining_quantity": 2.0, "buy_price": 500.0, "buy_currency": "USD", "current_price_idr": 15000000.0},
        {
            "remaining_quantity": 1.0,
            "buy_price": 300.0,
            "buy_currency": "USD",
            "current_price_idr": None,
        },  # Fallback scenario
    ]

    with patch("packages.api.backend.routers.deps.get_live_fx_rate", return_value=15000.0):
        total = _get_crypto_from_portfolio()

    # 2.0 * 15,000,000 + 1.0 * 300 * 15,000 = 30,000,000 + 4,500,000 = 34,500,000
    assert total == 34500000.0

    # Assert query does not contain correlated subquery in SELECT
    query_called = mock_db_query.call_args[0][1]
    assert "LEFT JOIN" in query_called
    assert "GROUP BY" in query_called
