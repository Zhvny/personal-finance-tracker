"""
Phase 15 — Net Worth Integration tests.

Covers packages/api/backend/finance/net_worth_service.py:

  * transfers NEVER change total cash / net worth (invariance)
  * cash_total == income - expense (transfers excluded) — transparency flag
  * investment positions add to net worth (latest price x remaining qty)
  * missing investment table/db -> 0 without crash
  * history: daily cumulative series, transfers excluded, ends today
  * renderer (format_net_worth_text)

Hermetic SQLite fixtures — safe names without canonical bridge targets.
"""
from datetime import date

import pytest

from packages.api.backend.finance import ledger_engine as ledger
from packages.api.backend.finance import net_worth_service as nw


@pytest.fixture
def ledger_db(tmp_path):
    path = str(tmp_path / "networth_ledger.sqlite")
    ledger.seed_defaults(path)
    return path


def _tx(ledger_db, ttype, amount, tx_date, category, description=None):
    accs = ledger.list_accounts(ledger_db, include_inactive=True)
    if not accs:
        accs = [ledger.create_account(ledger_db, "Default", account_type="cash")]
    return ledger.record_transaction(
        ledger_db, ttype=ttype, amount=amount, tx_date=tx_date,
        category=category, description=description, source="test",
        account_id=accs[0]["id"],
    )


def _accounts(ledger_db):
    return {a["name"]: a for a in ledger.list_accounts(ledger_db, include_inactive=True)}


def _transfer(ledger_db, from_id, to_id, amount, tx_date):
    ledger.record_transfer(
        ledger_db, from_account_id=from_id, to_account_id=to_id,
        amount=amount, tx_date=tx_date, check_balance=False,
    )


# ═════════════════════════════════════════════════════════════════════════════
# § Transfer neutrality
# ═════════════════════════════════════════════════════════════════════════════

def test_transfers_never_change_net_worth(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _tx(ledger_db, "expense", 2_000_000, date(2026, 8, 5), "food", description="Belanja")
    before = nw.build_net_worth(ledger_db, as_of=as_of)

    accs = _accounts(ledger_db)
    other = accs.get("Cash")
    if other is None:
        other = ledger.create_account(ledger_db, "Cash", account_type="cash")
    first = list(accs.values())[0]
    _transfer(ledger_db, first["id"], other["id"], 3_000_000, date(2026, 8, 10))
    after = nw.build_net_worth(ledger_db, as_of=as_of)

    assert before["net_worth"] == after["net_worth"] == 8_000_000.0
    # per-account balances moved, but the total did not
    assert after["cash_assets"] == 8_000_000.0
    assert after["transfers_transparent"] is True


def test_cash_equals_income_minus_expense(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _tx(ledger_db, "expense", 2_000_000, date(2026, 8, 5), "food", description="Belanja")
    accs = _accounts(ledger_db)
    other = accs.get("Cash")
    if other is None:
        other = ledger.create_account(ledger_db, "Cash", account_type="cash")
    first = list(accs.values())[0]
    _transfer(ledger_db, first["id"], other["id"], 3_000_000, date(2026, 8, 10))
    result = nw.build_net_worth(ledger_db, as_of=as_of)
    assert result["cash_assets"] == result["income_minus_expense"] == 8_000_000.0


# ═════════════════════════════════════════════════════════════════════════════
# § Investments
# ═════════════════════════════════════════════════════════════════════════════

def _seed_investment(investment_db):
    from packages.core.infrastructure.persistence.database import Database
    Database.execute(
        investment_db,
        "CREATE TABLE IF NOT EXISTS investments ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, asset_type TEXT, ticker TEXT,"
        " buy_price REAL, buy_currency TEXT, quantity REAL, remaining_quantity REAL, status TEXT)"
    )
    Database.execute(
        investment_db,
        "CREATE TABLE IF NOT EXISTS historical_prices ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, investment_id INTEGER, price_idr REAL)"
    )
    Database.execute(
        investment_db,
        "INSERT INTO investments (asset_type, ticker, buy_price, buy_currency, quantity, remaining_quantity, status)"
        " VALUES ('stock', 'BBRI', 4000, 'IDR', 100, 100, 'active')",
    )
    Database.execute(
        investment_db,
        "INSERT INTO historical_prices (investment_id, price_idr) VALUES (1, 5000)",
    )
    # sold position must be excluded
    Database.execute(
        investment_db,
        "INSERT INTO investments (asset_type, ticker, buy_price, buy_currency, quantity, remaining_quantity, status)"
        " VALUES ('crypto', 'BTC', 900000000, 'IDR', 0.1, 0.05, 'sold')",
    )


def test_investments_add_to_net_worth(tmp_path, ledger_db):
    investment_db = str(tmp_path / "networth_portfolio.sqlite")
    _seed_investment(investment_db)
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    result = nw.build_net_worth(ledger_db, investment_db, as_of=as_of)
    # 100 x 5000 = 500k (sold position excluded)
    assert result["investments"] == 500_000.0
    assert result["net_worth"] == 10_500_000.0


def test_missing_investment_table_returns_zero(tmp_path, ledger_db):
    empty_db = str(tmp_path / "networth_empty.sqlite")
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    result = nw.build_net_worth(ledger_db, empty_db, as_of=as_of)
    assert result["investments"] == 0.0
    assert result["net_worth"] == 10_000_000.0
    # None db also fine
    result2 = nw.build_net_worth(ledger_db, None, as_of=as_of)
    assert result2["investments"] == 0.0


# ═════════════════════════════════════════════════════════════════════════════
# § History
# ═════════════════════════════════════════════════════════════════════════════

def test_history_cumulative_excludes_transfers(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _tx(ledger_db, "expense", 2_000_000, date(2026, 8, 5), "food", description="Belanja")
    accs = _accounts(ledger_db)
    other = accs.get("Cash")
    if other is None:
        other = ledger.create_account(ledger_db, "Cash", account_type="cash")
    first = list(accs.values())[0]
    _transfer(ledger_db, first["id"], other["id"], 3_000_000, date(2026, 8, 10))

    result = nw.net_worth_history(ledger_db, days=30, as_of=as_of)
    assert result["days"] == 30
    assert len(result["series"]) == 30
    assert result["series"][0]["date"] == "2026-07-19"
    assert result["latest"]["cash_assets"] == 8_000_000.0
    # transfer (3jt) must NOT appear as a cash change between Aug 9 and Aug 11
    d9 = next(s for s in result["series"] if s["date"] == "2026-08-09")
    d11 = next(s for s in result["series"] if s["date"] == "2026-08-11")
    assert d9["cash_assets"] == d11["cash_assets"] == 8_000_000.0


def test_history_includes_investments_and_clamps_days(ledger_db, tmp_path):
    investment_db = str(tmp_path / "networth_portfolio2.sqlite")
    _seed_investment(investment_db)
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 5_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    result = nw.net_worth_history(ledger_db, investment_db, days=0, as_of=as_of)
    assert result["days"] == 90
    assert result["latest"]["net_worth"] == 5_500_000.0


# ═════════════════════════════════════════════════════════════════════════════
# § Renderer
# ═════════════════════════════════════════════════════════════════════════════

def test_format_net_worth_text(ledger_db):
    as_of = date(2026, 8, 17)
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    result = nw.build_net_worth(ledger_db, as_of=as_of)
    text = nw.format_net_worth_text(result)
    assert "Kekayaan Bersih" in text
    assert "Kas (semua rekening)" in text
    assert "Investasi" in text
    assert "Rp 10.000.000" in text
    assert "transfer antar rekening" in text.lower()
