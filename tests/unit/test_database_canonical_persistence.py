"""Regression tests for canonical financial persistence routing."""

import sqlite3

import pytest

from packages.api.backend.infrastructure.database import (
    CanonicalPersistenceUnavailableError as ApiCanonicalPersistenceUnavailableError,
)
from packages.api.backend.infrastructure.database import Database as ApiDatabase
from packages.api.backend.infrastructure.database import DatabaseManager as ApiDatabaseManager
from packages.core.infrastructure.persistence.database import (
    CanonicalPersistenceUnavailableError,
    Database,
    DatabaseManager,
)


def test_postgres_failure_never_falls_back_to_sqlite_for_financial_write(monkeypatch, tmp_path):
    """A failed canonical write must not create or modify an expense SQLite DB."""
    monkeypatch.delenv("ALPHA_FORCE_SQLITE", raising=False)
    db_path = tmp_path / "expense.db"
    monkeypatch.setenv("USE_SQLITE_ONLY", "true")

    def fail_postgres(*_args, **_kwargs):
        raise ConnectionError("postgres unavailable")

    monkeypatch.setattr(DatabaseManager, "execute", fail_postgres)

    with pytest.raises(CanonicalPersistenceUnavailableError, match="fallback is disabled"):
        Database.execute(
            str(db_path),
            "INSERT INTO expenses (amount) VALUES (?)",
            (125_000,),
        )

    assert not db_path.exists()


def test_api_bridge_postgres_failure_never_falls_back_to_sqlite_for_financial_write(monkeypatch, tmp_path):
    """The API-local bridge follows the same canonical persistence invariant."""
    monkeypatch.delenv("ALPHA_FORCE_SQLITE", raising=False)
    db_path = tmp_path / "income.db"

    def fail_postgres(*_args, **_kwargs):
        raise ConnectionError("postgres unavailable")

    monkeypatch.setattr(ApiDatabaseManager, "execute", fail_postgres)

    with pytest.raises(ApiCanonicalPersistenceUnavailableError, match="fallback is disabled"):
        ApiDatabase.execute(
            str(db_path),
            "INSERT INTO incomes (amount) VALUES (?)",
            (125_000,),
        )

    assert not db_path.exists()


@pytest.mark.parametrize(
    ("database", "manager", "error_type", "filename", "sql"),
    [
        (Database, DatabaseManager, CanonicalPersistenceUnavailableError, "expense.db", "SELECT * FROM expenses"),
        (
            ApiDatabase,
            ApiDatabaseManager,
            ApiCanonicalPersistenceUnavailableError,
            "income.db",
            "SELECT * FROM incomes",
        ),
    ],
)
def test_postgres_failure_never_reads_legacy_sqlite_for_financial_data(
    monkeypatch, tmp_path, database, manager, error_type, filename, sql
):
    """A failed canonical read must not expose stale data from a legacy DB."""
    monkeypatch.delenv("ALPHA_FORCE_SQLITE", raising=False)
    db_path = tmp_path / filename
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE expenses (amount INTEGER)")
        connection.execute("CREATE TABLE incomes (amount INTEGER)")
        connection.execute("INSERT INTO expenses (amount) VALUES (125000)")
        connection.execute("INSERT INTO incomes (amount) VALUES (125000)")

    def fail_postgres(*_args, **_kwargs):
        raise ConnectionError("postgres unavailable")

    monkeypatch.setattr(manager, "query", fail_postgres)

    with pytest.raises(error_type, match="read failed; legacy SQLite fallback is disabled"):
        database.query(str(db_path), sql)


def test_missing_postgres_financial_table_is_not_converted_to_empty_response(monkeypatch, tmp_path):
    """Schema drift must be visible instead of being reported as an empty ledger."""
    monkeypatch.delenv("ALPHA_FORCE_SQLITE", raising=False)
    db_path = tmp_path / "expense.db"
    monkeypatch.setattr(
        DatabaseManager,
        "query",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("relation expenses does not exist")),
    )

    with pytest.raises(CanonicalPersistenceUnavailableError, match="read failed"):
        Database.query(str(db_path), "SELECT * FROM expenses")


def test_explicit_nonfinancial_sqlite_path_remains_local(monkeypatch, tmp_path):
    """The safety rule does not remove explicitly local, non-financial storage."""
    db_path = tmp_path / "merchant_memory.db"
    monkeypatch.setattr(Database, "_is_postgres_target", staticmethod(lambda _path: False))

    Database.execute(str(db_path), "CREATE TABLE local_cache (value INTEGER)")
    Database.execute(str(db_path), "INSERT INTO local_cache (value) VALUES (?)", (1,))

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT value FROM local_cache").fetchone() == (1,)
