"""
Phase 11 — NL Finance Query tests.

Covers packages/api/backend/finance/nl_intent_service.py:

  * intent classification (rule-based, deterministic, no LLM)
  * params extraction (days / period / count)
  * every intent maps to a Phase 5-10 controlled computation
  * non-finance text returns None (falls through to draft flow)
  * explanation strings carry the computed numbers with reasoning
  * explicit intent+params execution path (LLM-classified contract)
  * Telegram renderer

Hermetic SQLite fixtures — safe names without canonical bridge targets.
"""
from datetime import date

import pytest

from packages.api.backend.finance import budget_service as bs
from packages.api.backend.finance import ledger_engine as ledger
from packages.api.backend.finance import nl_intent_service as nli


@pytest.fixture
def ledger_db(tmp_path):
    path = str(tmp_path / "nlintent_ledger.sqlite")
    ledger.seed_defaults(path)
    return path


@pytest.fixture
def budget_db(tmp_path):
    path = str(tmp_path / "nlintent_budget.sqlite")
    bs._ensure_budget_db(path)
    return path


def _tx(ledger_db, ttype, amount, tx_date, category, description=None):
    accounts = ledger.list_accounts(ledger_db, include_inactive=True)
    account_id = accounts[0]["id"]
    return ledger.record_transaction(
        ledger_db, ttype=ttype, amount=amount, tx_date=tx_date,
        category=category, description=description, source="test",
        account_id=account_id,
    )


def _seed_basic(ledger_db, as_of=date(2026, 8, 17)):
    _tx(ledger_db, "income", 10_000_000, date(2026, 8, 1), "Salary", description="Gaji")
    _tx(ledger_db, "expense", 500_000, date(2026, 8, 5), "Food", description="Belanja")
    _tx(ledger_db, "expense", 50_000, as_of, "Food", description="Kopi")


# ═════════════════════════════════════════════════════════════════════════════
# § Intent classification
# ═════════════════════════════════════════════════════════════════════════════

def test_detect_intents():
    assert nli.detect_finance_intent("berapa saldo saya") == {"intent": "GET_BALANCE", "params": {}}
    assert nli.detect_finance_intent("cek saldo") == {"intent": "GET_BALANCE", "params": {}}
    assert nli.detect_finance_intent("aman belanja berapa") == {"intent": "GET_SAFE_TO_SPEND", "params": {}}
    assert nli.detect_finance_intent("sisa aman 7 hari")["intent"] == "GET_SAFE_TO_SPEND"
    assert nli.detect_finance_intent("sisa aman 7 hari")["params"]["days"] == 7
    assert nli.detect_finance_intent("proyeksi bulan ini")["intent"] == "GET_FORECAST"
    assert nli.detect_finance_intent("proyeksi bulan ini")["params"]["days"] == 30
    assert nli.detect_finance_intent("prediksi 14 hari")["params"]["days"] == 14
    assert nli.detect_finance_intent("laporan minggu ini") == {
        "intent": "GET_REPORT", "params": {"period": "week"}
    }
    assert nli.detect_finance_intent("laporan hari ini")["params"]["period"] == "today"
    assert nli.detect_finance_intent("sisa budget bulan ini")["intent"] == "GET_BUDGET_STATUS"
    assert nli.detect_finance_intent("transaksi terakhir")["intent"] == "GET_RECENT"
    assert nli.detect_finance_intent("pengeluaran terakhir 3")["params"]["count"] == 3


def test_detect_non_finance_returns_none():
    assert nli.detect_finance_intent("") is None
    assert nli.detect_finance_intent("beli kopi 20rb") is None
    assert nli.detect_finance_intent("topup saldo 50rb") is None  # no question marker
    assert nli.detect_finance_intent("halo") is None


# ═════════════════════════════════════════════════════════════════════════════
# § Controlled computations
# ═════════════════════════════════════════════════════════════════════════════

def test_get_balance(ledger_db):
    _seed_basic(ledger_db)
    as_of = date(2026, 8, 17)
    result = nli.execute_finance_intent(ledger_db, text="berapa saldo saya", as_of=as_of)
    assert result["intent"] == "GET_BALANCE"
    assert result["data"]["total_balance"] == 9_450_000.0
    assert "Rp 9.450.000" in result["explanation"]


def test_get_safe_to_spend(ledger_db):
    _seed_basic(ledger_db)
    as_of = date(2026, 8, 17)
    result = nli.execute_finance_intent(ledger_db, text="sisa aman 7 hari", as_of=as_of)
    assert result["intent"] == "GET_SAFE_TO_SPEND"
    assert result["data"]["horizon_days"] == 7
    assert "Aman belanja" in result["explanation"] or "aman belanja" in result["explanation"]


def test_get_forecast(ledger_db):
    _seed_basic(ledger_db)
    as_of = date(2026, 8, 17)
    result = nli.execute_finance_intent(ledger_db, text="proyeksi bulan ini", as_of=as_of)
    assert result["intent"] == "GET_FORECAST"
    assert result["data"]["window_end"].startswith("2026-09-")
    assert "Proyeksi arus kas" in result["explanation"]


def test_get_report(ledger_db):
    _seed_basic(ledger_db)
    as_of = date(2026, 8, 17)
    result = nli.execute_finance_intent(ledger_db, text="laporan minggu ini", as_of=as_of)
    assert result["intent"] == "GET_REPORT"
    assert result["data"]["period"] == "week"
    assert "net" in result["explanation"]


def test_get_budget_status(ledger_db, budget_db):
    _seed_basic(ledger_db)
    as_of = date(2026, 8, 17)
    bs.set_budget_limit(budget_db, year=2026, month=8, category="Food", limit=1_000_000)
    result = nli.execute_finance_intent(
        ledger_db, budget_db=budget_db, text="sisa budget bulan ini", as_of=as_of
    )
    assert result["intent"] == "GET_BUDGET_STATUS"
    assert result["data"]["categories"][0]["category"] == "food"
    assert "budget" in result["explanation"].lower()


def test_get_recent(ledger_db):
    _seed_basic(ledger_db)
    as_of = date(2026, 8, 17)
    result = nli.execute_finance_intent(ledger_db, text="transaksi terakhir 2", as_of=as_of)
    assert result["intent"] == "GET_RECENT"
    assert len(result["data"]["transactions"]) == 2
    assert "Kopi" in result["explanation"]


def test_explicit_intent_params_path(ledger_db):
    """LLM-classified contract: caller passes intent+params, backend computes."""
    _seed_basic(ledger_db)
    as_of = date(2026, 8, 17)
    result = nli.execute_finance_intent(
        ledger_db, intent="GET_BALANCE", params={}, as_of=as_of
    )
    assert result["intent"] == "GET_BALANCE"
    assert result["data"]["total_balance"] == 9_450_000.0


def test_get_anomalies(ledger_db):
    _seed_basic(ledger_db)
    as_of = date(2026, 8, 17)
    result = nli.execute_finance_intent(ledger_db, text="ada anomali?", as_of=as_of)
    assert result["intent"] == "GET_ANOMALIES"
    assert result["data"]["window"]["start"] <= result["data"]["window"]["end"]


def test_get_health_score(ledger_db, budget_db):
    _seed_basic(ledger_db)
    as_of = date(2026, 8, 17)
    result = nli.execute_finance_intent(
        ledger_db, budget_db=budget_db, text="skor kesehatan keuangan", as_of=as_of
    )
    assert result["intent"] == "GET_HEALTH_SCORE"
    assert 0 <= result["data"]["total_score"] <= 100
    assert result["data"]["grade"] in ("Sehat", "Cukup", "Perlu Perhatian", "Kritis")
    assert "Skor kesehatan" in result["explanation"]


def test_get_net_worth(ledger_db, budget_db):
    _seed_basic(ledger_db)
    as_of = date(2026, 8, 17)
    result = nli.execute_finance_intent(
        ledger_db, budget_db=budget_db, text="berapa kekayaan saya", as_of=as_of
    )
    assert result["intent"] == "GET_NET_WORTH"
    assert result["data"]["cash_assets"] >= 0
    assert result["data"]["net_worth"] == result["data"]["cash_assets"] + result["data"]["investments"]
    assert "Kekayaan bersihmu" in result["explanation"]


def test_no_intent_returns_none(ledger_db):
    assert nli.execute_finance_intent(ledger_db, text="beli kopi 20rb") is None


# ═════════════════════════════════════════════════════════════════════════════
# § Telegram renderer
# ═════════════════════════════════════════════════════════════════════════════

def test_format_intent_reply_balance(ledger_db):
    _seed_basic(ledger_db)
    result = nli.execute_finance_intent(ledger_db, text="berapa saldo saya", as_of=date(2026, 8, 17))
    text = nli.format_intent_reply(result)
    assert "Saldo Kamu" in text
    assert "Rp 9.450.000" in text
    assert "Rincian rekening" in text


def test_format_intent_reply_safe_spend(ledger_db):
    _seed_basic(ledger_db)
    result = nli.execute_finance_intent(ledger_db, text="aman belanja berapa", as_of=date(2026, 8, 17))
    text = nli.format_intent_reply(result)
    assert "Aman Belanja" in text
    assert "Safe-to-spend" in text
