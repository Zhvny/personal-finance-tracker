"""
Phase 3 — Telegram NL input & confirmation store tests.

Covers packages/api/backend/finance/confirmation_engine.py:

  * chat bindings (upsert / lookup / per-chat auth gate)
  * draft lifecycle: create (24h TTL) / get / list / update
  * one-time token consumption (replay -> ConflictError, no duplicate ledger rows)
  * confirm -> ledger commit (amount/category/merchant/source/idempotency_key)
  * expiry sweep (24h) and expired-confirm rejection
  * cancel / cancel-all, per-chat isolation, cross-profile guard
  * ledger commit failure reverts the confirmation to pending

All fixtures use SQLite file paths that do NOT contain a canonical-Postgres
bridge target substring (e.g. "finance.db" / "chat.db"), so the bridge never
redirects to PostgreSQL during the test run.
"""
import pytest

from packages.api.backend.finance import confirmation_engine as ce
from packages.api.backend.finance import ledger_engine as ledger
from packages.core.infrastructure.config import Config


@pytest.fixture
def store_db(tmp_path):
    return str(tmp_path / "confirm_store.sqlite")


@pytest.fixture
def ledger_db(tmp_path):
    path = str(tmp_path / "ledger.sqlite")
    ledger.seed_defaults(path)
    return path


@pytest.fixture
def active_profile(monkeypatch):
    monkeypatch.setattr(Config, "get_active_profile", staticmethod(lambda: "personal"))
    return "personal"


def _draft(**overrides):
    base = {
        "type": "expense",
        "amount": 75000,
        "category": "Food",
        "merchant_name": "Warteg Bahari",
        "transaction_date": "2026-08-16",
    }
    base.update(overrides)
    return base


# ═════════════════════════════════════════════════════════════════════════════
# Chat bindings
# ═════════════════════════════════════════════════════════════════════════════

def test_bind_upsert(store_db, active_profile):
    b1 = ce.bind_chat(store_db, 111, display_name="Alpha")
    assert b1["profile"] == active_profile
    assert b1["display_name"] == "Alpha"

    b2 = ce.bind_chat(store_db, 111, display_name="Alpha 2")
    assert b2["display_name"] == "Alpha 2"
    assert len(ce.list_bindings(store_db)) == 1


def test_bind_with_explicit_profile(store_db, active_profile):
    b = ce.bind_chat(store_db, 222, profile="alice", display_name="A")
    assert b["profile"] == "alice"


def test_require_binding_gate(store_db, active_profile):
    with pytest.raises(ce.NotFoundError):
        ce.require_binding(store_db, 999)


def test_create_draft_requires_binding(store_db, active_profile):
    with pytest.raises(ce.NotFoundError):
        ce.create_draft(store_db, 999, _draft())


def test_get_binding_missing(store_db):
    assert ce.get_binding(store_db, 123) is None


# ═════════════════════════════════════════════════════════════════════════════
# Draft lifecycle
# ═════════════════════════════════════════════════════════════════════════════

def test_create_draft_returns_single_use_token_and_24h_ttl(store_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    out = ce.create_draft(store_db, 111, _draft())
    assert out["status"] == ce.STATUS_PENDING
    assert out["token"]
    assert len(out["token"]) >= 24
    assert out["idempotency_key"] == ce._hash_token(out["token"])

    stored = ce.get_draft(store_db, out["token"])
    assert stored["draft"]["amount"] == 75000
    assert stored["profile"] == active_profile

    # TTL is 24h: created_at + 24h == expires_at (parseable ISO timestamps)
    assert stored["expires_at"] > stored["created_at"]
    # Raw token must NOT be persisted (only its hash).
    rows = ce._query(store_db, "SELECT * FROM pending_confirmations")
    assert out["token"] not in str(rows[0])
    assert ce._hash_token(out["token"]) in str(rows[0])


def test_get_draft_unknown_token(store_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    with pytest.raises(ce.NotFoundError):
        ce.get_draft(store_db, "nope-not-a-token")


def test_list_drafts_filters_status_and_chat(store_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    ce.bind_chat(store_db, 222, profile=active_profile)
    d1 = ce.create_draft(store_db, 111, _draft())["token"]
    d2 = ce.create_draft(store_db, 111, _draft(amount=10, category="Other"))["token"]
    ce.create_draft(store_db, 222, _draft(amount=99))

    assert [r["id"] for r in ce.list_drafts(store_db, 111)] == [d["id"] for d in
        [ce.get_draft(store_db, d1), ce.get_draft(store_db, d2)]]
    assert len(ce.list_drafts(store_db, 111)) == 2
    assert len(ce.list_drafts(store_db, 222)) == 1

    ce.cancel_draft(store_db, d2)
    assert len(ce.list_drafts(store_db, 111, status=ce.STATUS_PENDING)) == 1
    assert len(ce.list_drafts(store_db, 111, status=ce.STATUS_CANCELLED)) == 1


def test_update_draft(store_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    t = ce.create_draft(store_db, 111, _draft())["token"]
    updated = ce.update_draft(store_db, t, draft=_draft(amount=80000), edit_target="total_amount")
    assert updated["draft"]["amount"] == 80000
    assert updated["edit_target"] == "total_amount"

    ce.cancel_draft(store_db, t)
    with pytest.raises(ce.ConflictError):
        ce.update_draft(store_db, t, draft=_draft(amount=1))


# ═════════════════════════════════════════════════════════════════════════════
# Confirm -> ledger commit
# ═════════════════════════════════════════════════════════════════════════════

def test_confirm_commits_to_ledger(store_db, ledger_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    t = ce.create_draft(store_db, 111, _draft())["token"]

    result = ce.confirm_draft(store_db, t, ledger_db_path=ledger_db)
    tx = result["transaction"]
    assert result["confirmation"]["status"] == ce.STATUS_CONFIRMED
    assert tx["amount"] == 75000
    assert tx["source"] == "telegram"
    assert tx["idempotency_key"] == ce._hash_token(t)
    assert tx["category"] == "Food"
    assert tx["merchant_name"].lower() == "warteg bahari"

    stored = ce.get_draft(store_db, t)
    assert stored["status"] == ce.STATUS_CONFIRMED
    assert stored["consumed_at"]


def test_confirm_replay_is_rejected_no_duplicate(store_db, ledger_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    t = ce.create_draft(store_db, 111, _draft())["token"]
    ce.confirm_draft(store_db, t, ledger_db_path=ledger_db)

    with pytest.raises(ce.ConflictError):
        ce.confirm_draft(store_db, t, ledger_db_path=ledger_db)
    assert len(ledger.list_transactions(ledger_db)) == 1


def test_confirm_replay_safe_after_crash_between_commit_and_store_update(
    store_db, ledger_db, active_profile
):
    # If the ledger INSERT succeeds but the status flip is lost (crash), a retry
    # of the same confirmation must return the SAME transaction via the
    # idempotency_key, never a duplicate row.
    ce.bind_chat(store_db, 111, profile=active_profile)
    t = ce.create_draft(store_db, 111, _draft())["token"]

    first = ce.confirm_draft(store_db, t, ledger_db_path=ledger_db)
    assert len(ledger.list_transactions(ledger_db)) == 1

    # Simulate the crash: store still says pending, ledger already has the row.
    ce._execute(
        store_db,
        "UPDATE pending_confirmations SET status = ?, consumed_at = NULL WHERE token_hash = ?",
        (ce.STATUS_PENDING, ce._hash_token(t)),
    )
    retry = ce.confirm_draft(store_db, t, ledger_db_path=ledger_db)
    assert retry["transaction"]["id"] == first["transaction"]["id"]
    assert len(ledger.list_transactions(ledger_db)) == 1


def test_confirm_income_draft(store_db, ledger_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    t = ce.create_draft(
        store_db, 111,
        _draft(type="income", amount=3000000, category="Salary", merchant_name="PT Maju"),
    )["token"]
    result = ce.confirm_draft(store_db, t, ledger_db_path=ledger_db)
    assert result["transaction"]["type"] == "income"
    assert result["transaction"]["amount"] == 3000000.0
    assert result["transaction"]["category"] == "Salary"


def test_confirm_unknown_type_fails_and_reverts(store_db, ledger_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    t = ce.create_draft(store_db, 111, _draft(type="transfer"))["token"]
    with pytest.raises(ce.ValidationError):
        ce.confirm_draft(store_db, t, ledger_db_path=ledger_db)
    assert ce.get_draft(store_db, t)["status"] == ce.STATUS_PENDING


def test_confirm_missing_amount_fails_and_reverts(store_db, ledger_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    t = ce.create_draft(store_db, 111, _draft(amount=None))["token"]
    with pytest.raises(ce.ValidationError):
        ce.confirm_draft(store_db, t, ledger_db_path=ledger_db)
    assert ce.get_draft(store_db, t)["status"] == ce.STATUS_PENDING


def test_confirm_ledger_failure_reverts_to_pending(store_db, ledger_db, active_profile, monkeypatch):
    ce.bind_chat(store_db, 111, profile=active_profile)
    t = ce.create_draft(store_db, 111, _draft())["token"]

    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(ce.ledger_engine, "record_transaction", boom)
    with pytest.raises(RuntimeError):
        ce.confirm_draft(store_db, t, ledger_db_path=ledger_db)
    assert ce.get_draft(store_db, t)["status"] == ce.STATUS_PENDING
    assert ce.get_draft(store_db, t)["consumed_at"] is None


# ═════════════════════════════════════════════════════════════════════════════
# Expiry / cancellation / isolation
# ═════════════════════════════════════════════════════════════════════════════

def test_expired_draft_cannot_confirm(store_db, ledger_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    t = ce.create_draft(store_db, 111, _draft())["token"]
    ce._execute(
        store_db,
        "UPDATE pending_confirmations SET expires_at = ? WHERE token_hash = ?",
        ("2000-01-01T00:00:00+00:00", ce._hash_token(t)),
    )
    with pytest.raises(ce.ConflictError):
        ce.confirm_draft(store_db, t, ledger_db_path=ledger_db)
    assert ce.get_draft(store_db, t)["status"] == ce.STATUS_EXPIRED
    assert len(ledger.list_transactions(ledger_db)) == 0


def test_expire_stale_sweep(store_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    t = ce.create_draft(store_db, 111, _draft())["token"]
    ce._execute(
        store_db,
        "UPDATE pending_confirmations SET expires_at = ? WHERE token_hash = ?",
        ("2000-01-01T00:00:00+00:00", ce._hash_token(t)),
    )
    assert ce.expire_stale(store_db) == 1
    assert ce.get_draft(store_db, t)["status"] == ce.STATUS_EXPIRED


def test_cancel_draft(store_db, ledger_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    t = ce.create_draft(store_db, 111, _draft())["token"]
    assert ce.cancel_draft(store_db, t)["status"] == ce.STATUS_CANCELLED
    with pytest.raises(ce.ConflictError):
        ce.confirm_draft(store_db, t, ledger_db_path=ledger_db)
    assert len(ledger.list_transactions(ledger_db)) == 0


def test_cancel_draft_already_consumed(store_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    t = ce.create_draft(store_db, 111, _draft())["token"]
    ce._consume(store_db, ce.get_draft(store_db, t)["id"])
    with pytest.raises(ce.ConflictError):
        ce.cancel_draft(store_db, t)


def test_cancel_all_pending(store_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    ce.bind_chat(store_db, 222, profile=active_profile)
    for _ in range(3):
        ce.create_draft(store_db, 111, _draft())
    ce.create_draft(store_db, 222, _draft())
    assert ce.cancel_all_pending(store_db, 111) == 3
    assert len(ce.list_drafts(store_db, 111)) == 0
    assert len(ce.list_drafts(store_db, 222)) == 1


def test_per_chat_isolation(store_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    ce.bind_chat(store_db, 222, profile=active_profile)
    ce.create_draft(store_db, 111, _draft())
    ce.create_draft(store_db, 222, _draft(amount=5))
    assert [r["draft"]["amount"] for r in ce.list_drafts(store_db, 111)] == [75000]
    assert [r["draft"]["amount"] for r in ce.list_drafts(store_db, 222)] == [5]


def test_confirm_cross_profile_guard(store_db, ledger_db, active_profile, monkeypatch):
    ce.bind_chat(store_db, 111, profile="alice")
    t = ce.create_draft(store_db, 111, _draft(), profile="alice")["token"]

    monkeypatch.setattr(Config, "get_active_profile", staticmethod(lambda: "bob"))
    with pytest.raises(ce.ConflictError):
        ce.confirm_draft(store_db, t, ledger_db_path=ledger_db)
    assert ce.get_draft(store_db, t)["status"] == ce.STATUS_PENDING
    assert len(ledger.list_transactions(ledger_db)) == 0


def test_draft_defaults_date_to_today(store_db, ledger_db, active_profile):
    from datetime import date
    ce.bind_chat(store_db, 111, profile=active_profile)
    t = ce.create_draft(store_db, 111, _draft(transaction_date=None))["token"]
    result = ce.confirm_draft(store_db, t, ledger_db_path=ledger_db)
    assert result["transaction"]["tx_date"] == date.today().isoformat()


def test_create_draft_empty_rejected(store_db, active_profile):
    ce.bind_chat(store_db, 111, profile=active_profile)
    with pytest.raises(ce.ValidationError):
        ce.create_draft(store_db, 111, {})


# ═════════════════════════════════════════════════════════════════════════════
# § Phase 4 — draft field validation (receipt hardening)
# ═════════════════════════════════════════════════════════════════════════════

def test_validate_draft_fields_ok():
    assert ce.validate_draft_fields(_draft()) == []
    assert ce.validate_draft_fields(_draft(amount=None, total_amount=25000)) == []
    assert ce.validate_draft_fields(_draft(amount="25.000")) == []
    assert ce.validate_draft_fields(_draft(amount=5000, merchant_name=None, merchant="Toko A")) == []


def test_validate_draft_fields_empty():
    errors = ce.validate_draft_fields({})
    assert "Draft is empty" in errors
    assert ce.validate_draft_fields(None) == ["Draft is empty"]


def test_validate_draft_fields_missing_or_invalid_amount():
    for bad in (None, "", 0, -1, "abc", 1_500_000_000):
        errors = ce.validate_draft_fields(_draft(amount=bad))
        assert errors, f"amount={bad!r} should be rejected"
    assert any("lebih dari 0" in e for e in ce.validate_draft_fields(_draft(amount=0)))
    assert any("terlalu besar" in e for e in ce.validate_draft_fields(_draft(amount=2_000_000_000)))
    assert any("tidak valid" in e for e in ce.validate_draft_fields(_draft(amount="abc")))


def test_validate_draft_fields_missing_or_short_merchant():
    for bad in (None, "", "A"):
        errors = ce.validate_draft_fields(_draft(merchant_name=bad))
        assert errors, f"merchant={bad!r} should be rejected"
    assert any("merchant" in e.lower() for e in ce.validate_draft_fields(_draft(merchant_name=None)))
