"""Regression tests for Investment Tracker canonical persistence and failure handling."""

from datetime import datetime
from decimal import Decimal

import pytest

from packages.core.domain.models.investment import Investment
from packages.core.infrastructure.investment_tracker.sqlite_repository import SQLiteInvestmentRepository
from packages.core.infrastructure.persistence.database import (
    CanonicalPersistenceUnavailableError,
    DatabaseManager,
)


def test_investment_repo_postgres_failure_never_falls_back_to_sqlite(monkeypatch, tmp_path):
    """Postgres failure during investment write must raise CanonicalPersistenceUnavailableError and not write SQLite."""
    monkeypatch.delenv("ALPHA_FORCE_SQLITE", raising=False)
    db_path = tmp_path / "portfolio.db"
    repo = SQLiteInvestmentRepository(db_path=str(db_path))

    def fail_postgres(*_args, **_kwargs):
        raise ConnectionError("PostgreSQL down")

    monkeypatch.setattr(DatabaseManager, "execute", fail_postgres)

    inv = Investment(
        asset_type="stock",
        ticker="AAPL",
        quantity=Decimal("10"),
        buy_price=Decimal("150"),
        buy_currency="USD",
        buy_date=datetime(2025, 1, 1),
    )

    with pytest.raises(CanonicalPersistenceUnavailableError, match="fallback is disabled"):
        repo.save(inv)

    # Confirm that SQLite file was not written with investment record
    if db_path.exists():
        import sqlite3

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if "investments" in tables:
                assert conn.execute("SELECT COUNT(*) FROM investments").fetchone()[0] == 0


def test_investment_repo_postgres_read_failure_never_reads_sqlite(monkeypatch, tmp_path):
    """Postgres read failure for investments must fail closed."""
    monkeypatch.delenv("ALPHA_FORCE_SQLITE", raising=False)
    db_path = tmp_path / "portfolio.db"
    repo = SQLiteInvestmentRepository(db_path=str(db_path))

    def fail_postgres(*_args, **_kwargs):
        raise ConnectionError("PostgreSQL read down")

    monkeypatch.setattr(DatabaseManager, "query", fail_postgres)

    with pytest.raises(CanonicalPersistenceUnavailableError, match="read failed"):
        repo.get_all_active()


def test_invalid_iso_date_raises_instead_of_fabricating_now(tmp_path):
    """Corrupt date strings must raise ValueError, never silently become now()."""
    repo = SQLiteInvestmentRepository(db_path=str(tmp_path / "portfolio.db"))
    inv_row = {
        "id": 1,
        "asset_type": "stock",
        "ticker": "AAPL",
        "quantity": "10",
        "buy_price": "150",
        "buy_currency": "USD",
        "buy_date": "not-a-date",
        "status": "holding",
        "remaining_quantity": "10",
    }
    sell_row = {
        "id": 1,
        "investment_id": 1,
        "sell_date": "not-a-date",
        "quantity": "1",
        "sell_price": "160",
        "fees": "0",
        "realized_pl": "10",
        "realized_pl_pct": "5",
    }
    with pytest.raises(ValueError):
        repo._map_row_to_investment(inv_row)
    with pytest.raises(ValueError):
        repo._map_row_to_sell_transaction(sell_row)
