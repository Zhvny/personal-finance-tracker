"""
Phase 2 — Unified Transaction & Account Model tests.

Covers the roadmap-mandated edge cases for packages/api/backend/finance/ledger_engine.py:

  * zero / negative / huge amounts (MAX_AMOUNT boundary)
  * same-day entries and date-range filtering (month/year/leap boundaries)
  * empty sets and missing account/category/merchant relations
  * duplicate / idempotency replay semantics
  * transfer neutrality (double-entry legs never distort a single balance)
  * backfill idempotency against legacy expenses/incomes rows
  * API route wiring / error mapping for routers/ledger.py

All fixtures use SQLite file paths that do NOT contain a canonical-Postgres
bridge target substring (e.g. "finance.db"), so the bridge never redirects to
PostgreSQL during the test run.
"""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from packages.api.backend.finance import ledger_engine as engine
from packages.api.backend.routers import ledger as ledger_router

# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(tmp_path):
    """Hermetic SQLite ledger DB (no Postgres bridge substring in the name)."""
    return str(tmp_path / "ledger.sqlite")


@pytest.fixture
def seeded(db):
    engine.seed_defaults(db)
    return db


def _default_account(db):
    return engine.list_accounts(db)[0]


def _cat(db, name, kind="expense"):
    engine.ensure_schema(db)
    return engine._get_or_create_category(db, name, kind)


@pytest.fixture
def legacy_db(tmp_path):
    """Legacy expenses/incomes DBs in the pre-unification schema."""
    exp_db = str(tmp_path / "legacy_exp.sqlite")
    inc_db = str(tmp_path / "legacy_inc.sqlite")
    for path, table, cols in (
        (
            exp_db,
            "expenses",
            (
                "id INTEGER PRIMARY KEY AUTOINCREMENT",
                "amount REAL NOT NULL",
                "description TEXT",
                "category TEXT",
                "date TEXT NOT NULL",
            ),
        ),
        (
            inc_db,
            "incomes",
            (
                "id INTEGER PRIMARY KEY AUTOINCREMENT",
                "amount REAL NOT NULL",
                "source TEXT",
                "income_type TEXT",
                "description TEXT",
                "date TEXT NOT NULL",
            ),
        ),
    ):
        conn = sqlite3.connect(path)
        conn.execute(f"CREATE TABLE {table} ({', '.join(cols)})")
        conn.commit()
        conn.close()

    exp_conn = sqlite3.connect(exp_db)
    exp_conn.executemany(
        "INSERT INTO expenses (amount, description, category, date) VALUES (?, ?, ?, ?)",
        [
            (15_000, "Nasi Padang", "Food", "2026-08-01"),
            (120_000, "Bensin", "Transport", "2026-08-02"),
            (50_000, "Belanja", "Other", "2026-07-31"),
        ],
    )
    exp_conn.commit()
    exp_conn.close()

    inc_conn = sqlite3.connect(inc_db)
    inc_conn.executemany(
        "INSERT INTO incomes (amount, source, income_type, description, date) VALUES (?, ?, ?, ?, ?)",
        [
            (5_000_000, "Acme Corp", "Salary", "Gaji bulanan", "2026-08-01"),
            (250_000, "Freelance", "Bonus", "Proyek X", "2026-08-05"),
        ],
    )
    inc_conn.commit()
    inc_conn.close()
    return exp_db, inc_db


# ═════════════════════════════════════════════════════════════════════════════
# Accounts / categories / merchants
# ═════════════════════════════════════════════════════════════════════════════

def test_seed_defaults_creates_default_account_and_categories(seeded):
    accounts = engine.list_accounts(seeded)
    assert len(accounts) == 1
    assert accounts[0]["name"] == "Default"
    assert accounts[0]["is_default"] is True
    cats = engine.list_categories(seeded)
    assert {c["name"] for c in cats} >= {
        "Food", "Transport", "Housing", "Entertainment", "Health",
        "Shopping", "Education", "Investment", "Other",
        "Salary", "Bonus", "Gift",
    }


def test_seed_defaults_is_idempotent(seeded):
    engine.seed_defaults(seeded)
    engine.seed_defaults(seeded)
    assert len(engine.list_accounts(seeded)) == 1
    assert len(engine.list_categories(seeded)) == 13


def test_create_account_validation(db):
    with pytest.raises(engine.ValidationError):
        engine.create_account(db, "", "bank")
    with pytest.raises(engine.ValidationError):
        engine.create_account(db, "Weird", "crypto")
    engine.create_account(db, "Wallet", "e-wallet", "IDR", 100_000)
    with pytest.raises(engine.DuplicateError):
        engine.create_account(db, "Wallet", "cash")


def test_account_delete_referenced_conflict(db):
    acc = engine.create_account(db, "Cash", "cash", "IDR", 0)
    cat = _cat(db, "Food")
    engine.record_transaction(
        db, ttype="expense", amount=10_000, tx_date="2026-08-01",
        account_id=acc["id"], category_id=cat["id"], idempotency_key="e:1",
    )
    with pytest.raises(engine.ConflictError):
        engine.delete_account(db, acc["id"])
    engine.delete_transaction(db, engine.list_transactions(db)[0]["id"])
    assert engine.delete_account(db, acc["id"]) is True


def test_merchant_normalization_and_lookup(db):
    m = engine.remember_merchant(
        db, "Starbucks Coffee #12", category="Food", display_name="Starbucks"
    )
    assert m["name"] == "starbucks coffee"
    assert engine.lookup_merchant(db, "Starbucks Coffee #12")["name"] == "starbucks coffee"
    assert engine.lookup_merchant(db, "No Such Place") is None
    engine.remember_merchant(db, "Starbucks Coffee #12")  # upsert, not duplicate
    matches = [x for x in engine.list_merchants(db) if x["name"] == "starbucks coffee"]
    assert len(matches) == 1
    assert matches[0]["edit_count"] == 2


def test_merchant_forget_referenced_conflict(db):
    acc = engine.create_account(db, "Cash", "cash", "IDR", 0)
    cat = _cat(db, "Food")
    m = engine.remember_merchant(db, "Warteg Bahari", category="Food")
    engine.record_transaction(
        db, ttype="expense", amount=12_000, tx_date="2026-08-01",
        account_id=acc["id"], category_id=cat["id"], merchant_id=m["id"],
        idempotency_key="e:1",
    )
    with pytest.raises(engine.ConflictError):
        engine.forget_merchant(db, m["id"])
    engine.delete_transaction(db, engine.list_transactions(db)[0]["id"])
    assert engine.forget_merchant(db, m["id"]) is True
    with pytest.raises(engine.NotFoundError):
        engine.forget_merchant(db, m["id"])


# ═════════════════════════════════════════════════════════════════════════════
# Transaction amounts: zero / negative / huge / boundary
# ═════════════════════════════════════════════════════════════════════════════

def _expense(db, **overrides):
    engine.ensure_schema(db)
    acc = engine.create_account(db, "Cash", "cash", "IDR", 0)
    cat = _cat(db, "Food")
    kw = dict(
        ttype="expense", amount=10_000, tx_date="2026-08-01",
        account_id=acc["id"], category_id=cat["id"],
    )
    kw.update(overrides)
    return engine.record_transaction(db, **kw)


def test_zero_amount_rejected(db):
    engine.ensure_schema(db)
    acc = engine.create_account(db, "Cash", "cash", "IDR", 0)
    cat = _cat(db, "Food")
    for amt in (0, 0.0):
        with pytest.raises(engine.ValidationError):
            engine.record_transaction(
                db, ttype="expense", amount=amt, tx_date="2026-08-01",
                account_id=acc["id"], category_id=cat["id"], idempotency_key="z",
            )


def test_negative_amount_rejected(db):
    engine.ensure_schema(db)
    acc = engine.create_account(db, "Cash", "cash", "IDR", 0)
    cat = _cat(db, "Food")
    for amt in (-1, -0.01):
        with pytest.raises(engine.ValidationError):
            engine.record_transaction(
                db, ttype="expense", amount=amt, tx_date="2026-08-01",
                account_id=acc["id"], category_id=cat["id"], idempotency_key="n",
            )


def test_max_amount_boundary_accepted(db):
    row = _expense(db, amount=float(engine.MAX_AMOUNT))
    assert row["amount"] == float(engine.MAX_AMOUNT)


def test_amount_above_max_rejected(db):
    with pytest.raises(engine.ValidationError):
        _expense(db, amount=float(engine.MAX_AMOUNT) + 0.01)


def test_amount_is_rounded_to_cents(db):
    row = _expense(db, amount=10_000.999)
    assert row["amount"] == 10_001.0


def test_future_date_rejected(db):
    with pytest.raises(engine.ValidationError):
        _expense(db, tx_date="9999-01-01")


# ═════════════════════════════════════════════════════════════════════════════
# Dates: leap day, month/year boundaries, same-day ordering
# ═════════════════════════════════════════════════════════════════════════════

def test_leap_day_accepted(db):
    row = _expense(db, tx_date="2024-02-29")
    assert row["tx_date"] == "2024-02-29"


def test_month_year_boundary_filtering(db):
    acc = engine.create_account(db, "Cash", "cash", "IDR", 0)
    cat = _cat(db, "Food")
    engine.record_transaction(
        db, ttype="expense", amount=1_000, tx_date="2025-12-31",
        account_id=acc["id"], category_id=cat["id"], idempotency_key="a",
    )
    engine.record_transaction(
        db, ttype="expense", amount=2_000, tx_date="2026-01-01",
        account_id=acc["id"], category_id=cat["id"], idempotency_key="b",
    )
    engine.record_transaction(
        db, ttype="expense", amount=3_000, tx_date="2026-02-01",
        account_id=acc["id"], category_id=cat["id"], idempotency_key="c",
    )
    jan = engine.list_transactions(db, start_date="2026-01-01", end_date="2026-01-31")
    assert {t["idempotency_key"] for t in jan} == {"b"}
    boundary = engine.list_transactions(
        db, start_date="2025-12-31", end_date="2026-01-01"
    )
    assert {t["idempotency_key"] for t in boundary} == {"a", "b"}


def test_same_day_entries_order_by_id_and_balance(db):
    acc = engine.create_account(db, "Cash", "cash", "IDR", 1_000_000)
    cat = _cat(db, "Food")
    for i, amt in enumerate((10_000, 20_000, 30_000)):
        engine.record_transaction(
            db, ttype="expense", amount=amt, tx_date="2026-08-10",
            account_id=acc["id"], category_id=cat["id"], idempotency_key=f"same:{i}",
        )
    rows = engine.list_transactions(db, ttype="expense")
    assert [t["amount"] for t in rows] == [30_000, 20_000, 10_000]  # id DESC
    assert engine.account_balance(db, acc["id"]) == 940_000.0


# ═════════════════════════════════════════════════════════════════════════════
# Empty sets and missing relations
# ═════════════════════════════════════════════════════════════════════════════

def test_empty_database(db):
    engine.ensure_schema(db)
    assert engine.list_accounts(db) == []
    assert engine.list_transactions(db) == []
    assert engine.list_transfers(db) == []
    assert engine.list_categories(db) == []
    assert engine.list_merchants(db) == []


def test_missing_relations_raise_not_found(db):
    cat = _cat(db, "Food")
    acc = engine.create_account(db, "Cash", "cash", "IDR", 0)
    with pytest.raises(engine.NotFoundError):
        engine.record_transaction(
            db, ttype="expense", amount=5_000, tx_date="2026-08-01",
            account_id=999_999, category_id=cat["id"], idempotency_key="x",
        )
    with pytest.raises(engine.NotFoundError):
        engine.record_transaction(
            db, ttype="expense", amount=5_000, tx_date="2026-08-01",
            account_id=acc["id"], category_id=999_999, idempotency_key="x",
        )
    with pytest.raises(engine.NotFoundError):
        engine.record_transaction(
            db, ttype="expense", amount=5_000, tx_date="2026-08-01",
            account_id=acc["id"], merchant_id=999_999, idempotency_key="x",
        )
    assert engine.get_transaction(db, 1) is None
    assert engine.get_account(db, 999_999) is None
    assert engine.get_category(db, 999_999) is None
    with pytest.raises(engine.NotFoundError):
        engine.delete_transaction(db, 1)
    with pytest.raises(engine.NotFoundError):
        engine.account_balance(db, 999_999)
    assert engine.get_transfer(db, "missing") is None  # missing pair -> None


# ═════════════════════════════════════════════════════════════════════════════
# Idempotency / duplicate semantics
# ═════════════════════════════════════════════════════════════════════════════

def test_idempotency_key_replay_returns_same_row(db):
    engine.ensure_schema(db)
    acc = engine.create_account(db, "Cash", "cash", "IDR", 0)
    cat = _cat(db, "Food")
    kw = dict(
        ttype="expense", amount=7_500, tx_date="2026-08-01",
        account_id=acc["id"], category_id=cat["id"], idempotency_key="dup:1",
    )
    first = engine.record_transaction(db, **kw)
    replay = engine.record_transaction(db, **kw)
    assert replay["id"] == first["id"]
    assert len(engine.list_transactions(db)) == 1


def test_different_keys_create_distinct_rows(db):
    acc = engine.create_account(db, "Cash", "cash", "IDR", 0)
    cat = _cat(db, "Food")
    a = engine.record_transaction(
        db, ttype="expense", amount=1_000, tx_date="2026-08-01",
        account_id=acc["id"], category_id=cat["id"], idempotency_key="k1",
    )
    b = engine.record_transaction(
        db, ttype="expense", amount=1_000, tx_date="2026-08-01",
        account_id=acc["id"], category_id=cat["id"], idempotency_key="k2",
    )
    assert a["id"] != b["id"]
    assert len(engine.list_transactions(db)) == 2


# ═════════════════════════════════════════════════════════════════════════════
# Transfers: neutrality, guards, atomic deletes
# ═════════════════════════════════════════════════════════════════════════════

def test_transfer_neutrality_and_direction(db):
    a = engine.create_account(db, "A", "bank", "IDR", 1_000_000)
    b = engine.create_account(db, "B", "cash", "IDR", 500_000)
    engine.record_transfer(
        db, from_account_id=a["id"], to_account_id=b["id"],
        amount=200_000, tx_date="2026-08-01", pair_key="t1",
    )
    engine.record_transfer(
        db, from_account_id=b["id"], to_account_id=a["id"],
        amount=50_000, tx_date="2026-08-02", pair_key="t2",
    )
    assert engine.account_balance(db, a["id"]) == 850_000.0
    assert engine.account_balance(db, b["id"]) == 650_000.0
    # Global wealth unchanged: 1_500_000 both before and after.
    assert 850_000.0 + 650_000.0 == 1_500_000.0
    # Two legs exist per transfer, paired once.
    transfers = engine.list_transfers(db)
    assert len(transfers) == 2
    assert len(engine.list_transactions(db, ttype="transfer")) == 4


def test_transfer_same_account_rejected(db):
    a = engine.create_account(db, "A", "bank", "IDR", 100_000)
    with pytest.raises(engine.ValidationError):
        engine.record_transfer(
            db, from_account_id=a["id"], to_account_id=a["id"],
            amount=1_000, tx_date="2026-08-01", pair_key="t1",
        )


def test_transfer_missing_account_rejected(db):
    a = engine.create_account(db, "A", "bank", "IDR", 100_000)
    with pytest.raises(engine.NotFoundError):
        engine.record_transfer(
            db, from_account_id=a["id"], to_account_id=99_999,
            amount=1_000, tx_date="2026-08-01", pair_key="t1",
        )


def test_transfer_insufficient_funds_rejected(db):
    a = engine.create_account(db, "A", "bank", "IDR", 10_000)
    b = engine.create_account(db, "B", "cash", "IDR", 0)
    with pytest.raises(engine.InsufficientFundsError):
        engine.record_transfer(
            db, from_account_id=a["id"], to_account_id=b["id"],
            amount=20_000, tx_date="2026-08-01", pair_key="t1",
        )


def test_transfer_check_balance_false_allows_overdraft(db):
    a = engine.create_account(db, "A", "bank", "IDR", 10_000)
    b = engine.create_account(db, "B", "cash", "IDR", 0)
    engine.record_transfer(
        db, from_account_id=a["id"], to_account_id=b["id"],
        amount=20_000, tx_date="2026-08-01", pair_key="t1", check_balance=False,
    )
    assert engine.account_balance(db, a["id"]) == -10_000.0
    assert engine.account_balance(db, b["id"]) == 20_000.0


def test_transfer_replay_is_idempotent(db):
    a = engine.create_account(db, "A", "bank", "IDR", 100_000)
    b = engine.create_account(db, "B", "cash", "IDR", 0)
    kw = dict(
        from_account_id=a["id"], to_account_id=b["id"],
        amount=30_000, tx_date="2026-08-01", pair_key="t1",
    )
    engine.record_transfer(db, **kw)
    replay = engine.record_transfer(db, **kw)
    assert replay["pair_key"] == "t1"
    assert len(engine.list_transfers(db)) == 1
    assert len(engine.list_transactions(db, ttype="transfer")) == 2


def test_delete_transfer_restores_balances(db):
    a = engine.create_account(db, "A", "bank", "IDR", 100_000)
    b = engine.create_account(db, "B", "cash", "IDR", 100_000)
    engine.record_transfer(
        db, from_account_id=a["id"], to_account_id=b["id"],
        amount=40_000, tx_date="2026-08-01", pair_key="t1",
    )
    engine.delete_transfer(db, "t1")
    assert engine.account_balance(db, a["id"]) == 100_000.0
    assert engine.account_balance(db, b["id"]) == 100_000.0
    assert engine.list_transfers(db) == []
    assert engine.list_transactions(db, ttype="transfer") == []


def test_delete_transfer_missing_raises(db):
    with pytest.raises(engine.NotFoundError):
        engine.delete_transfer(db, "nope")


def test_delete_transaction_on_transfer_leg_rejected(db):
    a = engine.create_account(db, "A", "bank", "IDR", 100_000)
    b = engine.create_account(db, "B", "cash", "IDR", 0)
    engine.record_transfer(
        db, from_account_id=a["id"], to_account_id=b["id"],
        amount=10_000, tx_date="2026-08-01", pair_key="t1",
    )
    leg = engine.list_transactions(db, ttype="transfer")[0]
    with pytest.raises(engine.ConflictError):
        engine.delete_transaction(db, leg["id"])


def test_account_balance_as_of_cutoff(db):
    a = engine.create_account(db, "A", "bank", "IDR", 1_000_000)
    cat = _cat(db, "Food")
    engine.record_transaction(
        db, ttype="expense", amount=100_000, tx_date="2026-08-01",
        account_id=a["id"], category_id=cat["id"], idempotency_key="e1",
    )
    engine.record_transaction(
        db, ttype="expense", amount=200_000, tx_date="2026-08-15",
        account_id=a["id"], category_id=cat["id"], idempotency_key="e2",
    )
    assert engine.account_balance(db, a["id"], as_of="2026-08-10") == 900_000.0
    assert engine.account_balance(db, a["id"]) == 700_000.0


# ═════════════════════════════════════════════════════════════════════════════
# Backfill from legacy expenses / incomes
# ═════════════════════════════════════════════════════════════════════════════

def test_backfill_maps_legacy_rows(db, legacy_db):
    exp_db, inc_db = legacy_db
    result = engine.backfill_from_legacy(db, exp_db, inc_db)
    assert result["expenses"] == {"total": 3, "inserted": 3, "skipped": 0, "errors": 0}
    assert result["incomes"] == {"total": 2, "inserted": 2, "skipped": 0, "errors": 0}
    txs = engine.list_transactions(db)
    assert len(txs) == 5
    by_key = {t["idempotency_key"]: t for t in txs}
    assert set(by_key) == {"expense:1", "expense:2", "expense:3", "income:1", "income:2"}
    exp1 = by_key["expense:1"]
    assert exp1["type"] == "expense"
    assert exp1["amount"] == 15_000.0
    assert exp1["category"] == "Food"
    assert exp1["tx_date"] == "2026-08-01"
    inc1 = by_key["income:1"]
    assert inc1["type"] == "income"
    assert inc1["amount"] == 5_000_000.0
    assert inc1["category"] == "Salary"
    assert inc1["description"] == "Gaji bulanan"
    # Everything lands on the default account.
    default_id = result["account_id"]
    assert all(t["account_id"] == default_id for t in txs)


def test_backfill_is_idempotent(db, legacy_db):
    exp_db, inc_db = legacy_db
    first = engine.backfill_from_legacy(db, exp_db, inc_db)
    second = engine.backfill_from_legacy(db, exp_db, inc_db)
    assert first["expenses"]["inserted"] == 3
    assert first["incomes"]["inserted"] == 2
    assert second["expenses"] == {"total": 3, "inserted": 0, "skipped": 3, "errors": 0}
    assert second["incomes"] == {"total": 2, "inserted": 0, "skipped": 2, "errors": 0}
    assert len(engine.list_transactions(db)) == 5


def test_backfill_dry_run_inserts_nothing(db, legacy_db):
    exp_db, inc_db = legacy_db
    result = engine.backfill_from_legacy(db, exp_db, inc_db, dry_run=True)
    assert result["expenses"] == {"total": 3, "inserted": 3, "skipped": 0, "errors": 0}
    assert result["incomes"] == {"total": 2, "inserted": 2, "skipped": 0, "errors": 0}
    assert engine.list_transactions(db) == []


# ═════════════════════════════════════════════════════════════════════════════
# API router: wiring, route order, error mapping
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def api_client(monkeypatch, tmp_path):
    # monkeypatch auto-restore — dulu os.environ.pop() menghapus DEV_MODE milik
    # .env permanen sehingga semua test sesi berikutnya kehilangan dev-bypass (401).
    monkeypatch.setenv("FINANCE_TRACKER_DEV_MODE", "1")
    db_path = str(tmp_path / "api_ledger.sqlite")
    monkeypatch.setattr(ledger_router, "_ledger_db", lambda: db_path)
    app = FastAPI()
    app.include_router(ledger_router.router)
    with TestClient(app) as client:
        yield client


def test_api_static_subroutes_not_shadowed_by_dynamic_route(api_client):
    # Regression: /api/transactions/transfers must not 422 via {tx_id}.
    r = api_client.get("/api/transactions/transfers")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_api_error_mapping(api_client):
    bad_zero = api_client.post(
        "/api/transactions",
        json={"type": "expense", "amount": 0, "tx_date": "2026-08-01"},
    )
    assert bad_zero.status_code == 400
    missing = api_client.get("/api/accounts/999")
    assert missing.status_code == 404
    duplicate = api_client.post("/api/accounts", json={"name": "Cash", "type": "cash"})
    assert duplicate.status_code == 200
    dup_again = api_client.post("/api/accounts", json={"name": "Cash", "type": "cash"})
    assert dup_again.status_code == 409
    future = api_client.post(
        "/api/transactions",
        json={"type": "expense", "amount": 5_000, "tx_date": "9999-01-01"},
    )
    assert future.status_code == 400


def test_api_transfer_and_balance_flow(api_client):
    a = api_client.post("/api/accounts", json={"name": "A", "type": "bank", "opening_balance": 100_000}).json()
    b = api_client.post("/api/accounts", json={"name": "B", "type": "cash"}).json()
    r = api_client.post(
        "/api/transactions/transfer",
        json={
            "from_account_id": a["id"], "to_account_id": b["id"],
            "amount": 30_000, "tx_date": "2026-08-01", "pair_key": "t-api-1",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["from_account_id"] == a["id"]
    assert data["to_account_id"] == b["id"]
    assert data["amount"] == 30_000.0
    bal_a = api_client.get(f"/api/accounts/{a['id']}/balance").json()["balance"]
    bal_b = api_client.get(f"/api/accounts/{b['id']}/balance").json()["balance"]
    assert bal_a == 70_000.0
    assert bal_b == 30_000.0
    transfers = api_client.get("/api/transactions/transfers").json()["items"]
    assert len(transfers) == 1
    get_pair = api_client.get("/api/transactions/transfer/t-api-1")
    assert get_pair.status_code == 200
    assert api_client.delete("/api/transactions/transfer/t-api-1").status_code == 200
    assert api_client.get("/api/transactions/transfer/t-api-1").status_code == 404
    assert api_client.get("/api/transactions/transfers").json()["items"] == []


def test_api_category_merchant_flow(api_client):
    cat = api_client.post("/api/categories", json={"name": "GoFood", "kind": "expense"}).json()
    assert cat["id"] > 0
    mer = api_client.post(
        "/api/merchants", json={"name": "GoFood Mart", "category": "GoFood"}
    ).json()
    assert mer["merchant"]["name"] == "gofood mart"
    listed = api_client.get("/api/merchants").json()["items"]
    assert any(m["name"] == "gofood mart" for m in listed)
    assert api_client.delete(f"/api/merchants/{mer['id']}").status_code == 200


def test_api_backfill_flow(api_client, legacy_db):
    exp_db, inc_db = legacy_db
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "packages.api.backend.routers.ledger.Config.get_db_path",
        lambda key: {   # only used for expense/income legacy paths here
            "expense": exp_db,
            "income": inc_db,
        }.get(key, ""),
    )
    try:
        dry = api_client.post("/api/transactions/backfill?dry_run=true")
        assert dry.status_code == 200
        assert dry.json()["expenses"]["inserted"] == 3
        assert len(api_client.get("/api/transactions").json()["items"]) == 0
        real = api_client.post("/api/transactions/backfill")
        assert real.status_code == 200
        assert real.json()["expenses"]["inserted"] == 3
        assert real.json()["incomes"]["inserted"] == 2
        assert len(api_client.get("/api/transactions").json()["items"]) == 5
    finally:
        monkeypatch.undo()
