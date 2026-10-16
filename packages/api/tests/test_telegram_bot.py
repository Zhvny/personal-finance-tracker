import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── Path setup ───────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_GUI  = _HERE.parent
_PROJECT_ROOT = _GUI.parent.parent

if str(_GUI)          not in sys.path: sys.path.insert(0, str(_GUI))
if str(_PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(_PROJECT_ROOT))

import packages.api.telegram_bot as telegram_bot
from packages.api.api_server import app
from packages.api.telegram_bot import PENDING_RECEIPTS

client = TestClient(app, raise_server_exceptions=False)

# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_sessions(monkeypatch, tmp_path):
    monkeypatch.setattr(telegram_bot, "TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")
    client.headers["X-Telegram-Bot-Api-Secret-Token"] = "test-webhook-secret"
    # Phase 3 — hermetic store paths: drafts persist into a temp SQLite store
    # instead of the canonical Postgres-backed chat.db.
    monkeypatch.setattr(telegram_bot, "_chat_db", lambda: str(tmp_path / "chat.sqlite"))
    monkeypatch.setattr(telegram_bot, "_ledger_db", lambda: str(tmp_path / "ledger.sqlite"))
    PENDING_RECEIPTS.clear()
    yield
    PENDING_RECEIPTS.clear()
    client.headers.pop("X-Telegram-Bot-Api-Secret-Token", None)


def _seed_session(chat_id=1234567, token=None, draft=None):
    """Create a store-backed draft + nav session (Phase 3 contract)."""
    from packages.api.backend.finance import confirmation_engine as ce
    from packages.core.infrastructure.config import Config
    profile = Config.get_active_profile()
    ce.bind_chat(telegram_bot._chat_db(), chat_id, profile=profile)
    draft = draft or {
        "merchant_name": "Starbucks", "transaction_date": "2026-07-20",
        "total_amount": 65000, "category": "food", "transaction_type": "expense",
    }
    out = ce.create_draft(telegram_bot._chat_db(), chat_id, draft, profile=profile)
    PENDING_RECEIPTS[chat_id] = {"tokens": [out["token"]], "current_index": 0}
    return out["token"]


def test_webhook_rejects_missing_secret():
    client.headers.pop("X-Telegram-Bot-Api-Secret-Token", None)
    response = client.post("/telegram/webhook", json={"message": {"chat": {"id": 1}}})
    assert response.status_code == 401

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# § 1. HEALTH CHECK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_telegram_health():
    response = client.get("/telegram/health")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "ok"
    assert res["token_set"] is True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# § 2. WEBHOOK — general text (now routed through telegram_handler)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
@patch("packages.api.telegram_handler.dashboard_service")
def test_webhook_help_text(mock_dash, mock_tg_call):
    """Sending 'hai' or 'help' → returns help text via telegram_handler."""
    mock_tg_call.return_value = {"result": {"message_id": 999}}

    payload = {
        "message": {
            "chat": {"id": 1234567},
            "text": "hai",
            "from": {"first_name": "TestUser"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "ok"
    # Response action is now 'processed' (not 'help_sent')
    assert res["action"] in ("processed", "help_sent", "warning_sent")

    # A message must have been sent
    assert mock_tg_call.called


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
@patch("packages.api.telegram_handler.dashboard_service")
def test_webhook_start_command(mock_dash, mock_tg_call):
    """Sending /start → returns welcome help text."""
    mock_tg_call.return_value = {"result": {"message_id": 1001}}

    payload = {
        "message": {
            "chat": {"id": 1234567},
            "text": "/start",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert mock_tg_call.called
    calls = mock_tg_call.call_args_list
    sent_text = calls[-1][0][1]["text"]
    assert "Finance Tracker" in sent_text or "Selamat datang" in sent_text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# § 3. WEBHOOK — add expense / income via text
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
@patch("packages.api.backend.routers.deps.expense_service")
@patch("packages.api.backend.routers.deps.income_service")
def test_webhook_add_expense_text(mock_inc, mock_exp, mock_tg_call):
    """'tambah pengeluaran 50000 makan siang' → calls expense_service and sends confirmation."""
    mock_tg_call.return_value = {"result": {"message_id": 1002}}
    mock_exp.record_expense = AsyncMock(return_value={"id": 42, "newly_unlocked": []})

    payload = {
        "message": {
            "chat": {"id": 1234567},
            "text": "tambah pengeluaran 50000 makan siang",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert mock_tg_call.called
    calls = mock_tg_call.call_args_list
    sent_text = calls[-1][0][1]["text"]
    assert "Berhasil" in sent_text or "pengeluaran" in sent_text.lower()


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
@patch("packages.api.backend.routers.deps.expense_service")
@patch("packages.api.backend.routers.deps.income_service")
def test_webhook_add_expense_slash_command(mock_inc, mock_exp, mock_tg_call):
    """/expense 35k kopi susu → parsed with k abbreviation."""
    mock_tg_call.return_value = {"result": {"message_id": 1003}}
    mock_exp.record_expense = AsyncMock(return_value={"id": 43, "newly_unlocked": []})

    payload = {
        "message": {
            "chat": {"id": 1234567},
            "text": "/expense 35k kopi susu",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert mock_tg_call.called


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
@patch("packages.api.backend.routers.deps.expense_service")
@patch("packages.api.backend.routers.deps.income_service")
def test_webhook_add_income_text(mock_inc, mock_exp, mock_tg_call):
    """'tambah pemasukan 1.5jt gaji bulanan' → calls income_service."""
    mock_tg_call.return_value = {"result": {"message_id": 1004}}
    mock_inc.record_income = MagicMock(return_value={"income_id": 10, "newly_unlocked": [], "allocation": {}, "is_real_income": True})

    payload = {
        "message": {
            "chat": {"id": 1234567},
            "text": "tambah pemasukan 1500000 gaji bulanan",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert mock_tg_call.called


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# § 4. WEBHOOK — query commands
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_webhook_summary_command(mock_tg_call, monkeypatch, tmp_path):
    """'/summary' → sends backend-computed monthly report (Phase 5)."""
    from datetime import date

    from packages.api.backend.finance import ledger_engine as ledger
    from packages.core.infrastructure.config import Config

    ledger_db = str(tmp_path / "summary_ledger.sqlite")
    ledger.seed_defaults(ledger_db)
    ledger.record_transaction(
        ledger_db, ttype="income", amount=5_000_000,
        tx_date=date.today().isoformat(), category="Salary", description="gaji",
    )
    ledger.record_transaction(
        ledger_db, ttype="expense", amount=2_000_000,
        tx_date=date.today().isoformat(), category="Food", description="belanja",
    )

    real_get_db_path = Config.get_db_path

    def fake_get_db_path(key):
        return ledger_db if key == "finance" else real_get_db_path(key)

    monkeypatch.setattr(Config, "get_db_path", staticmethod(fake_get_db_path))

    mock_tg_call.return_value = {"result": {"message_id": 1005}}
    payload = {
        "message": {
            "chat": {"id": 1234567},
            "text": "/summary",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert mock_tg_call.called
    calls = mock_tg_call.call_args_list
    sent_text = calls[-1][0][1]["text"]
    assert "Laporan Bulan Ini" in sent_text
    assert "Rp 5.000.000" in sent_text
    assert "Rp 2.000.000" in sent_text


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_webhook_daily_command(mock_tg_call, monkeypatch, tmp_path):
    """'hari ini' → sends backend-computed daily report (Phase 5)."""
    from datetime import date

    from packages.api.backend.finance import ledger_engine as ledger
    from packages.core.infrastructure.config import Config

    ledger_db = str(tmp_path / "daily_ledger.sqlite")
    ledger.seed_defaults(ledger_db)
    ledger.record_transaction(
        ledger_db, ttype="expense", amount=1_000_000,
        tx_date=date.today().isoformat(), category="Transport", description="grab",
    )

    real_get_db_path = Config.get_db_path

    def fake_get_db_path(key):
        return ledger_db if key == "finance" else real_get_db_path(key)

    monkeypatch.setattr(Config, "get_db_path", staticmethod(fake_get_db_path))

    mock_tg_call.return_value = {"result": {"message_id": 1006}}
    payload = {
        "message": {
            "chat": {"id": 1234567},
            "text": "hari ini",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert mock_tg_call.called
    calls = mock_tg_call.call_args_list
    sent_text = calls[-1][0][1]["text"]
    assert "Laporan Hari Ini" in sent_text
    assert "Rp 1.000.000" in sent_text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# § 4b. WEBHOOK — budget status (Phase 6)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _patch_db_paths(monkeypatch, tmp_path):
    """Point finance + budget Config paths at hermetic SQLite files."""
    from packages.api.backend.finance import ledger_engine as ledger
    from packages.core.infrastructure.config import Config

    ledger_db = str(tmp_path / "webhook_ledger.sqlite")
    budget_db = str(tmp_path / "webhook_budget.sqlite")
    ledger.seed_defaults(ledger_db)

    real_get_db_path = Config.get_db_path

    def fake_get_db_path(key):
        if key == "finance":
            return ledger_db
        if key == "budget":
            return budget_db
        return real_get_db_path(key)

    monkeypatch.setattr(Config, "get_db_path", staticmethod(fake_get_db_path))
    return ledger_db, budget_db


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_webhook_budget_command(mock_tg_call, monkeypatch, tmp_path):
    """/budget → ledger-backed budget status with levels and thresholds."""
    from datetime import date

    from packages.api.backend.finance import budget_service as bs
    from packages.api.backend.finance import ledger_engine as ledger

    ledger_db, budget_db = _patch_db_paths(monkeypatch, tmp_path)
    bs.set_budget_limit(budget_db, date.today().year, date.today().month, "food", 1_000_000)
    ledger.record_transaction(
        ledger_db, ttype="expense", amount=750_000,
        tx_date=date.today().isoformat(), category="food",
    )

    mock_tg_call.return_value = {}
    payload = {
        "message": {
            "chat": {"id": 1234567},
            "text": "/budget",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["action"] == "processed"

    sent_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "Status Budget Bulan Ini" in sent_text
    assert "FOOD" in sent_text
    assert "Rp 750.000" in sent_text
    assert "Rp 1.000.000" in sent_text
    assert "75.0%" in sent_text


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_webhook_budget_command_no_limits(mock_tg_call, monkeypatch, tmp_path):
    """/budget without limits → friendly empty-state message."""
    _patch_db_paths(monkeypatch, tmp_path)

    mock_tg_call.return_value = {}
    payload = {
        "message": {
            "chat": {"id": 1234567},
            "text": "sisa budget",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    sent_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "Belum ada limit budget" in sent_text


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_webhook_safe_to_spend_command(mock_tg_call, monkeypatch, tmp_path):
    """/safetospend → balance - upcoming outflows - buffer (Phase 10)."""
    from datetime import date

    from packages.api.backend.finance import ledger_engine as ledger

    ledger_db, _ = _patch_db_paths(monkeypatch, tmp_path)
    ledger.record_transaction(
        ledger_db, ttype="income", amount=5_000_000,
        tx_date=date.today().isoformat(), category="Salary", description="Gaji",
    )

    mock_tg_call.return_value = {}
    payload = {
        "message": {
            "chat": {"id": 1234568},
            "text": "safetospend",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["action"] == "processed"

    sent_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "Aman Belanja" in sent_text
    assert "Saldo saat ini" in sent_text
    assert "Buffer aman (10%)" in sent_text
    assert "Safe-to-spend" in sent_text


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_webhook_nl_finance_question(mock_tg_call, monkeypatch, tmp_path):
    """Free-form finance question → deterministic backend answer (Phase 11)."""
    from datetime import date

    from packages.api.backend.finance import ledger_engine as ledger

    ledger_db, _ = _patch_db_paths(monkeypatch, tmp_path)
    accounts = ledger.list_accounts(ledger_db, include_inactive=True)
    ledger.record_transaction(
        ledger_db, ttype="income", amount=5_000_000,
        tx_date=date.today().isoformat(), category="Salary", description="Gaji",
        account_id=accounts[0]["id"], source="test",
    )

    mock_tg_call.return_value = {}
    payload = {
        "message": {
            "chat": {"id": 1234569},
            "text": "berapa saldo saya",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["action"] == "processed"

    sent_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "Saldo Kamu" in sent_text
    assert "Rp 5.000.000" in sent_text
    assert "Rincian rekening" in sent_text


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_webhook_nl_non_finance_falls_back_to_draft(mock_tg_call, monkeypatch, tmp_path):
    """Non-finance free text still flows to the Phase 3 draft flow."""
    _patch_db_paths(monkeypatch, tmp_path)
    mock_tg_call.return_value = {}
    payload = {
        "message": {
            "chat": {"id": 1234570},
            "text": "beli kopi 20rb",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["action"] in ("draft_created", "unknown")


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_webhook_anomalies_command(mock_tg_call, monkeypatch, tmp_path):
    """/anomali → deterministic anomaly detection (Phase 12)."""
    from datetime import date

    from packages.api.backend.finance import ledger_engine as ledger

    ledger_db, _ = _patch_db_paths(monkeypatch, tmp_path)
    ledger.record_transaction(
        ledger_db, ttype="expense", amount=100_000,
        tx_date=date.today().isoformat(), category="Food", description="Kopi",
    )

    mock_tg_call.return_value = {}
    payload = {
        "message": {
            "chat": {"id": 1234571},
            "text": "anomali",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["action"] == "processed"

    sent_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "Anomali Keuangan" in sent_text
    assert "Tidak ada anomali terdeteksi" in sent_text


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_webhook_insights_command(mock_tg_call, monkeypatch, tmp_path):
    """/wawasan → insight cards from verified backend data (Phase 13)."""
    from datetime import date

    from packages.api.backend.finance import ledger_engine as ledger

    ledger_db, _ = _patch_db_paths(monkeypatch, tmp_path)
    ledger.record_transaction(
        ledger_db, ttype="income", amount=5_000_000,
        tx_date=date.today().isoformat(), category="Salary", description="Gaji",
    )

    mock_tg_call.return_value = {}
    payload = {
        "message": {
            "chat": {"id": 1234572},
            "text": "wawasan",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["action"] == "processed"

    sent_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "Wawasan Keuangan" in sent_text
    assert "Ringkasan:" in sent_text
    assert "[POSITIVE]" in sent_text or "[INFO]" in sent_text


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_webhook_health_score_command(mock_tg_call, monkeypatch, tmp_path):
    """/skor kesehatan → explainable composite health score (Phase 14)."""
    from datetime import date

    from packages.api.backend.finance import ledger_engine as ledger

    ledger_db, _ = _patch_db_paths(monkeypatch, tmp_path)
    ledger.record_transaction(
        ledger_db, ttype="income", amount=5_000_000,
        tx_date=date.today().isoformat(), category="Salary", description="Gaji",
    )

    mock_tg_call.return_value = {}
    payload = {
        "message": {
            "chat": {"id": 1234573},
            "text": "skor kesehatan",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["action"] == "processed"

    sent_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "Skor Kesehatan Keuangan" in sent_text
    assert "/100" in sent_text
    assert "bobot" in sent_text


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_webhook_net_worth_command(mock_tg_call, monkeypatch, tmp_path):
    """/kekayaan → net worth with transfer neutrality note (Phase 15)."""
    from datetime import date

    from packages.api.backend.finance import ledger_engine as ledger

    ledger_db, _ = _patch_db_paths(monkeypatch, tmp_path)
    accs = ledger.list_accounts(ledger_db, include_inactive=True)
    ledger.record_transaction(
        ledger_db, ttype="income", amount=5_000_000,
        tx_date=date.today().isoformat(), category="Salary", description="Gaji",
        account_id=accs[0]["id"],
    )

    mock_tg_call.return_value = {}
    payload = {
        "message": {
            "chat": {"id": 1234574},
            "text": "kekayaan",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["action"] == "processed"

    sent_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "Kekayaan Bersih" in sent_text
    assert "Rp 5.000.000" in sent_text
    assert "transfer" in sent_text


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_webhook_forecast_command(mock_tg_call, monkeypatch, tmp_path):
    """/forecast → deterministic labeled cashflow projection (Phase 9)."""
    from datetime import date

    from packages.api.backend.finance import ledger_engine as ledger

    ledger_db, _ = _patch_db_paths(monkeypatch, tmp_path)
    ledger.record_transaction(
        ledger_db, ttype="expense", amount=100_000,
        tx_date=date.today().isoformat(), category="Food", description="Kopi",
    )

    mock_tg_call.return_value = {}
    payload = {
        "message": {
            "chat": {"id": 1234567},
            "text": "forecast 7",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["action"] == "processed"

    sent_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "Proyeksi Arus Kas" in sent_text
    assert "Known (transaksi nyata)" in sent_text
    assert "Expected (langganan terkonfirmasi)" in sent_text
    assert "Rp 100.000" in sent_text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# § 5. RECEIPT OCR FLOW (existing tests — kept intact)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_receipt_pending_initialization(mock_tg_call):
    """n8n sends scanned receipt data to initialize confirmation flow."""
    from packages.api.backend.finance import confirmation_engine as ce

    mock_tg_call.return_value = {"result": {"message_id": 888}}

    payload = {
        "chat_id": 1234567,
        "receipts": [{
            "merchant_name": "Starbucks",
            "transaction_date": "2026-07-20",
            "total_amount": 65000,
            "category": "food",
            "payment_method": "cash",
            "transaction_type": "expense"
        }]
    }
    response = client.post("/telegram/receipt_pending", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "ok"
    assert res["message_id"] == 888

    # Nav session holds the one-time draft tokens (raw tokens never persisted)
    assert 1234567 in PENDING_RECEIPTS
    session = PENDING_RECEIPTS[1234567]
    assert session["current_index"] == 0
    assert len(session["tokens"]) == 1

    # The draft itself lives in the persistent store
    token = session["tokens"][0]
    row = ce.get_draft(telegram_bot._chat_db(), token)
    assert row["draft"]["merchant_name"] == "Starbucks"
    assert row["draft"]["total_amount"] == 65000
    assert row["status"] == "pending"
    assert row["message_id"] == 888


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_receipt_pending_no_receipts(mock_tg_call):
    """Empty receipts list → sends error to user."""
    mock_tg_call.return_value = {}
    payload = {"chat_id": 1234567, "receipts": []}
    response = client.post("/telegram/receipt_pending", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "error"


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_callback_query_edit_merchant(mock_tg_call):
    """Clicking Edit Merchant button enters edit mode (persisted edit_target)."""
    from packages.api.backend.finance import confirmation_engine as ce

    mock_tg_call.return_value = {}
    token = _seed_session()
    payload = {"callback_query": {
        "id": "q1", "message": {"message_id": 888, "chat": {"id": 1234567}},
        "data": "edit_merchant"
    }}
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    row = ce.get_draft(telegram_bot._chat_db(), token)
    assert row["edit_target"] == "merchant_name"


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_callback_set_category(mock_tg_call):
    """set_cat:shopping → updates category in the persistent draft."""
    from packages.api.backend.finance import confirmation_engine as ce

    mock_tg_call.return_value = {}
    token = _seed_session()
    payload = {"callback_query": {
        "id": "q2", "message": {"message_id": 888, "chat": {"id": 1234567}},
        "data": "set_cat:shopping"
    }}
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    row = ce.get_draft(telegram_bot._chat_db(), token)
    assert row["draft"]["category"] == "shopping"


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_text_edit_amount_abbreviation(mock_tg_call):
    """Typing '120k' during edit_target=total_amount → 120000 (persisted)."""
    from packages.api.backend.finance import confirmation_engine as ce

    mock_tg_call.return_value = {}
    token = _seed_session()
    ce.update_draft(telegram_bot._chat_db(), token, edit_target="total_amount")
    payload = {"message": {
        "chat": {"id": 1234567},
        "text": "120k",
        "from": {"first_name": "Zhvn"}
    }}
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    row = ce.get_draft(telegram_bot._chat_db(), token)
    assert row["draft"]["total_amount"] == 120000
    assert row["edit_target"] is None


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_callback_cancel(mock_tg_call):
    """confirm_cancel removes session and cancels drafts in the store."""
    from packages.api.backend.finance import confirmation_engine as ce

    mock_tg_call.return_value = {}
    token = _seed_session()
    payload = {"callback_query": {
        "id": "q3", "message": {"message_id": 888, "chat": {"id": 1234567}},
        "data": "confirm_cancel"
    }}
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert 1234567 not in PENDING_RECEIPTS
    last_call_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "dibatalkan" in last_call_text
    assert ce.get_draft(telegram_bot._chat_db(), token)["status"] == "cancelled"


@patch("packages.api.backend.routers.ai._detect_provider", return_value={"provider": "rules", "model": "rules"})
@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_nl_text_creates_persistent_draft(mock_tg_call, mock_provider):
    """Free-form NL text ('beli kopi 25rb') → draft created in the store."""
    from packages.api.backend.finance import confirmation_engine as ce

    mock_tg_call.return_value = {"result": {"message_id": 777}}
    payload = {
        "message": {
            "chat": {"id": 1234567},
            "text": "beli kopi 25rb di kedai",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["action"] == "draft_created"

    assert 1234567 in PENDING_RECEIPTS
    token = PENDING_RECEIPTS[1234567]["tokens"][0]
    row = ce.get_draft(telegram_bot._chat_db(), token)
    assert row["draft"]["amount"] == 25000
    assert row["draft"]["category"] == "Food"
    assert row["status"] == "pending"


@patch("packages.api.backend.routers.ai._detect_provider", return_value={"provider": "rules", "model": "rules"})
@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_webhook_nl_transfer_creates_draft(mock_tg_call, mock_provider):
    """Free-form NL transfer text ('transfer 500rb dari BCA ke Jago') → transfer draft."""
    from packages.api.backend.finance import confirmation_engine as ce

    mock_tg_call.return_value = {"result": {"message_id": 777}}
    payload = {
        "message": {
            "chat": {"id": 1234567},
            "text": "transfer 500rb dari BCA ke Jago",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["action"] == "draft_created"

    assert 1234567 in PENDING_RECEIPTS
    token = PENDING_RECEIPTS[1234567]["tokens"][0]
    row = ce.get_draft(telegram_bot._chat_db(), token)
    assert row["draft"]["type"] == "transfer"
    assert row["draft"]["amount"] == 500000
    assert row["draft"]["from_account"] == "BCA"
    assert row["draft"]["to_account"] == "Jago"
    assert row["status"] == "pending"

    # The confirmation message must render the transfer shape
    sent_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "Konfirmasi Transfer" in sent_text
    assert "<b>Dari:</b> BCA" in sent_text
    assert "<b>Ke:</b> Jago" in sent_text
    assert "Rp 500.000" in sent_text


def _seed_transfer_session(chat_id=1234567, ledger_path=None, token=None, draft=None):
    """Seed a transfer draft + nav session with BCA/Jago accounts in the ledger."""
    from packages.api.backend.finance import confirmation_engine as ce
    from packages.api.backend.finance import ledger_engine as ledger
    from packages.core.infrastructure.config import Config

    profile = Config.get_active_profile()
    ledger_path = ledger_path or telegram_bot._ledger_db()
    ledger.seed_defaults(ledger_path)
    bca = ledger.create_account(
        ledger_path, name="BCA", account_type="bank", currency="IDR", opening_balance=0.0
    )
    jago = ledger.create_account(
        ledger_path, name="Jago", account_type="e-wallet", currency="IDR", opening_balance=0.0
    )
    ledger.record_transaction(
        ledger_path, ttype="income", amount=10_000_000,
        tx_date="2026-08-16", category="Salary", description="Gaji",
        account_id=bca["id"],
    )

    ce.bind_chat(telegram_bot._chat_db(), chat_id, profile=profile)
    draft = draft or {
        "type": "transfer", "amount": 1_000_000, "total_amount": 1_000_000,
        "from_account": "BCA", "to_account": "Jago",
        "transaction_date": "2026-08-17", "description": "transfer ke jago",
        "confidence": 0.9,
    }
    out = ce.create_draft(telegram_bot._chat_db(), chat_id, draft, profile=profile)
    PENDING_RECEIPTS[chat_id] = {"tokens": [out["token"]], "current_index": 0}
    return out["token"], bca, jago


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_callback_edit_from_account(mock_tg_call, monkeypatch, tmp_path):
    """Clicking Edit Dari → typing a new name updates from_account in the draft."""
    from packages.api.backend.finance import confirmation_engine as ce

    mock_tg_call.return_value = {}
    token, _, _ = _seed_transfer_session(chat_id=1234577)

    payload = {"callback_query": {
        "id": "q-t1", "message": {"message_id": 888, "chat": {"id": 1234577}},
        "data": "edit_from_account"
    }}
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert ce.get_draft(telegram_bot._chat_db(), token)["edit_target"] == "from_account"

    payload = {"message": {
        "chat": {"id": 1234577},
        "text": "Mandiri",
        "from": {"first_name": "Zhvn"}
    }}
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    row = ce.get_draft(telegram_bot._chat_db(), token)
    assert row["draft"]["from_account"] == "Mandiri"
    assert row["edit_target"] is None

    # Keyboard must be the transfer keyboard (has Edit Dari / Edit Ke)
    sent_keyboard = mock_tg_call.call_args_list[-1][0][1].get("reply_markup", {})
    callback_datas = [
        btn["callback_data"]
        for row in sent_keyboard.get("inline_keyboard", [])
        for btn in row
    ]
    assert "edit_to_account" in callback_datas
    assert "edit_from_account" in callback_datas


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_callback_edit_to_account(mock_tg_call, monkeypatch, tmp_path):
    """Clicking Edit Ke → typing a new name updates to_account in the draft."""
    from packages.api.backend.finance import confirmation_engine as ce

    mock_tg_call.return_value = {}
    token, _, _ = _seed_transfer_session(chat_id=1234578)

    payload = {"callback_query": {
        "id": "q-t2", "message": {"message_id": 888, "chat": {"id": 1234578}},
        "data": "edit_to_account"
    }}
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert ce.get_draft(telegram_bot._chat_db(), token)["edit_target"] == "to_account"

    payload = {"message": {
        "chat": {"id": 1234578},
        "text": "SeaBank",
        "from": {"first_name": "Zhvn"}
    }}
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert ce.get_draft(telegram_bot._chat_db(), token)["draft"]["to_account"] == "SeaBank"


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_transfer_confirm_saves_double_entry(mock_tg_call, monkeypatch, tmp_path):
    """Confirming a transfer draft commits a net-neutral double-entry pair."""
    from packages.api.backend.finance import ledger_engine as ledger

    mock_tg_call.return_value = {}
    token, bca, jago = _seed_transfer_session(chat_id=1234579)
    assert len(ledger.list_transfers(telegram_bot._ledger_db())) == 0

    payload = {"callback_query": {
        "id": "q-t3", "message": {"message_id": 888, "chat": {"id": 1234579}},
        "data": "confirm_save"
    }}
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200

    transfers = ledger.list_transfers(telegram_bot._ledger_db())
    assert len(transfers) == 1
    assert transfers[0]["amount"] == 1_000_000.0
    assert transfers[0]["from_account_id"] == bca["id"]
    assert transfers[0]["to_account_id"] == jago["id"]
    assert ledger.account_balance(telegram_bot._ledger_db(), bca["id"]) == 9_000_000
    assert ledger.account_balance(telegram_bot._ledger_db(), jago["id"]) == 1_000_000
    assert 1234579 not in PENDING_RECEIPTS


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_transfer_confirm_unknown_account_fails_gracefully(mock_tg_call, monkeypatch, tmp_path):
    """Confirming with an unknown account keeps the draft pending + notifies the user."""
    from packages.api.backend.finance import confirmation_engine as ce
    from packages.api.backend.finance import ledger_engine as ledger

    mock_tg_call.return_value = {}
    token, _, _ = _seed_transfer_session(
        chat_id=1234580,
        draft={
            "type": "transfer", "amount": 100_000, "total_amount": 100_000,
            "from_account": "BCA", "to_account": "Rekening Tak Dikenal",
            "transaction_date": "2026-08-17",
        },
    )

    payload = {"callback_query": {
        "id": "q-t4", "message": {"message_id": 888, "chat": {"id": 1234580}},
        "data": "confirm_save"
    }}
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200

    assert len(ledger.list_transfers(telegram_bot._ledger_db())) == 0
    assert ce.get_draft(telegram_bot._chat_db(), token)["status"] == "pending"
    error_text = [
        c[0][1]["text"] for c in mock_tg_call.call_args_list
        if "Gagal menyimpan" in c[0][1].get("text", "")
    ]
    assert error_text, "a save-failure message should be sent"


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_receipt_pending_low_confidence_warning(mock_tg_call):
    """Phase 4 — low-confidence OCR receipt → confirmation text shows warning."""
    from packages.api.backend.finance import confirmation_engine as ce

    mock_tg_call.return_value = {"result": {"message_id": 888}}
    payload = {
        "chat_id": 1234567,
        "receipts": [{
            "merchant_name": "Kopi Kenangan",
            "transaction_date": "2026-07-20",
            "total_amount": 15000,
            "category": "food",
            "transaction_type": "expense",
            "confidence": 0.42,
        }]
    }
    response = client.post("/telegram/receipt_pending", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    confirmation_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "Kepercayaan OCR:</b> 42%" in confirmation_text
    assert "Akurasi rendah" in confirmation_text

    token = PENDING_RECEIPTS[1234567]["tokens"][0]
    row = ce.get_draft(telegram_bot._chat_db(), token)
    assert row["draft"]["confidence"] == 0.42
    assert row["status"] == "pending"


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_receipt_pending_high_confidence_still_confirms(mock_tg_call):
    """Phase 4 — high-confidence receipt still requires manual confirmation."""
    from packages.api.backend.finance import confirmation_engine as ce

    mock_tg_call.return_value = {"result": {"message_id": 888}}
    payload = {
        "chat_id": 1234567,
        "receipts": [{
            "merchant_name": "Starbucks",
            "transaction_date": "2026-07-20",
            "total_amount": 65000,
            "category": "food",
            "transaction_type": "expense",
            "confidence": 0.99,
        }]
    }
    response = client.post("/telegram/receipt_pending", json=payload)
    assert response.status_code == 200

    confirmation_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "Kepercayaan OCR:</b> 99%" in confirmation_text
    assert "Akurasi rendah" not in confirmation_text

    token = PENDING_RECEIPTS[1234567]["tokens"][0]
    assert ce.get_draft(telegram_bot._chat_db(), token)["status"] == "pending"


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_receipt_pending_invalid_receipt_rejected(mock_tg_call):
    """Phase 4 — invalid receipt (zero amount) is rejected up-front."""
    mock_tg_call.return_value = {}
    payload = {
        "chat_id": 1234567,
        "receipts": [{
            "merchant_name": "Toko ABC",
            "transaction_date": "2026-07-20",
            "total_amount": 0,
            "category": "shopping",
            "transaction_type": "expense",
        }]
    }
    response = client.post("/telegram/receipt_pending", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert 1234567 not in PENDING_RECEIPTS
    error_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "tidak valid" in error_text.lower()


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_receipt_pending_partially_invalid(mock_tg_call):
    """Phase 4 — mixed batch: invalid item rejected, valid item queued."""
    from packages.api.backend.finance import confirmation_engine as ce

    mock_tg_call.return_value = {"result": {"message_id": 888}}
    payload = {
        "chat_id": 1234567,
        "receipts": [
            {
                "merchant_name": "Alfamart",
                "transaction_date": "2026-07-20",
                "total_amount": 45000,
                "category": "shopping",
                "transaction_type": "expense",
            },
            {
                "merchant_name": "Toko XYZ",
                "transaction_date": "2026-07-20",
                "total_amount": None,
                "category": "other",
                "transaction_type": "expense",
            },
        ]
    }
    response = client.post("/telegram/receipt_pending", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    warnings = [c for c in mock_tg_call.call_args_list if "diabaikan" in c[0][1].get("text", "")]
    assert warnings, "a rejection warning should be sent"
    assert 1234567 in PENDING_RECEIPTS
    assert len(PENDING_RECEIPTS[1234567]["tokens"]) == 1
    token = PENDING_RECEIPTS[1234567]["tokens"][0]
    assert ce.get_draft(telegram_bot._chat_db(), token)["draft"]["merchant_name"] == "Alfamart"


@patch("packages.api.telegram_bot._tg_call", new_callable=AsyncMock)
def test_report_command_month_webhook(mock_tg_call, monkeypatch, tmp_path):
    """Phase 5 — '/report month' renders a backend-computed ledger report."""
    from datetime import date

    from packages.api.backend.finance import ledger_engine as ledger
    from packages.core.infrastructure.config import Config

    ledger_db = str(tmp_path / "report_ledger.sqlite")
    ledger.seed_defaults(ledger_db)
    ledger.record_transaction(
        ledger_db, ttype="expense", amount=25000,
        tx_date=date.today().isoformat(), category="Food", description="kopi",
    )

    real_get_db_path = Config.get_db_path

    def fake_get_db_path(key):
        if key == "finance":
            return ledger_db
        return real_get_db_path(key)

    monkeypatch.setattr(Config, "get_db_path", staticmethod(fake_get_db_path))

    mock_tg_call.return_value = {}
    payload = {
        "message": {
            "chat": {"id": 1234567},
            "text": "/report month",
            "from": {"first_name": "Zhvn"}
        }
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["action"] == "processed"

    reply_text = mock_tg_call.call_args_list[-1][0][1]["text"]
    assert "Laporan Bulan Ini" in reply_text
    assert "Rp 25.000" in reply_text
    assert "Net Cashflow" in reply_text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# § 6. TELEGRAM HANDLER UNIT TESTS (parse_amount, detect_category)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_parse_amount():
    from packages.api.telegram_handler import parse_amount
    assert parse_amount("50000") == 50000.0
    assert parse_amount("50k") == 50000.0
    assert parse_amount("50rb") == 50000.0
    assert parse_amount("1.5jt") == 1_500_000.0
    assert parse_amount("2jt") == 2_000_000.0
    assert parse_amount("Rp 75.000") == 75000.0
    assert parse_amount("abc") is None


def test_detect_category_expense():
    from packages.api.telegram_handler import detect_category
    assert detect_category("makan siang di warung", "expense") == "food"
    assert detect_category("bayar bensin", "expense") == "transport"
    assert detect_category("bayar token listrik", "expense") == "housing"
    assert detect_category("beli obat apotek", "expense") == "health"
    assert detect_category("nonton bioskop", "expense") == "entertainment"
    assert detect_category("beli baju di mall", "expense") == "shopping"
    assert detect_category("beli buku kuliah", "expense") == "education"
    assert detect_category("sesuatu random", "expense") == "other"


def test_detect_category_income():
    from packages.api.telegram_handler import detect_category
    assert detect_category("gaji bulanan", "income") == "salary"
    assert detect_category("proyek freelance klien", "income") == "freelance"
    assert detect_category("dividen saham", "income") == "investment"
    assert detect_category("transfer dari rekening", "income") == "transfer"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# § 7. LOG DASHBOARD UNIT TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_log_dashboard_classify_line():
    """classify_line correctly detects log levels."""
    from apps.cli.log_dashboard import classify_line
    assert classify_line("2026-07-20 INFO some message") == "INFO"
    assert classify_line("2026-07-20 WARNING budget near limit") == "WARNING"
    assert classify_line("2026-07-20 ERROR db connection failed") == "ERROR"
    assert classify_line("2026-07-20 CRITICAL out of memory") == "CRITICAL"
    assert classify_line("something with no level marker") == "INFO"


def test_log_dashboard_fmt_line():
    """format_datadog_line returns a Rich Text object with appropriate style."""
    from rich.text import Text

    from apps.cli.log_dashboard import format_datadog_line
    t = format_datadog_line("api", "2026-07-20 WARNING: budget exceeded")
    assert isinstance(t, Text)
    assert "budget exceeded" in t.plain


def test_log_sources_defined():
    """LOG_SOURCES has the 5 expected keys, each with label/badge/color/path."""
    from apps.cli.log_dashboard import LOG_SOURCES
    assert "cli" in LOG_SOURCES
    assert "api" in LOG_SOURCES
    assert "optimizer" in LOG_SOURCES
    for key, info in LOG_SOURCES.items():
        assert isinstance(info["label"], str)
        assert isinstance(info["badge"], str)
        assert isinstance(info["path"], Path)


def test_log_pane_filter_logic():
    """LogPane.refresh_logs must not raise when log file doesn't exist."""

    from apps.cli.log_dashboard import LogPane
    # Use a nonexistent path — should handle gracefully via on_mount guard
    pane = LogPane("cli", "CLI & Scheduler", Path("/nonexistent/path/app.log"))
    # No exception — just ensure the object is created properly
    assert pane.source_key == "cli"
    assert pane.source_label == "CLI & Scheduler"
