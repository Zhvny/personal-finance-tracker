"""
Telegram NL transfer input — confirmation engine tests.

Covers packages/api/backend/finance/confirmation_engine.py transfer support:

  * validate_draft_fields accepts well-formed transfer drafts and rejects
    drafts missing accounts / with identical source & destination
  * confirm_draft commits a transfer as a double-entry pair (net-neutral,
    balances shift from source to destination only)
  * account references resolve by numeric id, exact name, and normalized
    (fuzzy) name; unknown accounts fail with a clear ValidationError
  * failed ledger commits (same account, unknown account, insufficient
    funds) revert the confirmation to pending
  * pair_key = token_hash makes confirm replay-safe (no duplicate pairs)
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


@pytest.fixture
def two_accounts(ledger_db):
    bca = ledger.create_account(
        ledger_db,
        name="BCA",
        account_type="bank",
        currency="IDR",
        opening_balance=0.0,
    )
    jago = ledger.create_account(
        ledger_db,
        name="Jago",
        account_type="e-wallet",
        currency="IDR",
        opening_balance=0.0,
    )
    ledger.record_transaction(
        ledger_db,
        ttype="income",
        amount=10_000_000,
        tx_date="2026-08-16",
        category="Salary",
        description="Gaji",
        account_id=bca["id"],
    )
    return bca, jago


def _transfer_draft(**overrides):
    base = {
        "type": "transfer",
        "amount": 1_000_000,
        "from_account": "BCA",
        "to_account": "Jago",
        "transaction_date": "2026-08-17",
        "description": "transfer ke jago",
        "confidence": 0.9,
    }
    base.update(overrides)
    return base


def _confirm(store_db, ledger_db_path, chat_id, draft, profile):
    ce.bind_chat(store_db, chat_id, profile=profile)
    out = ce.create_draft(store_db, chat_id, draft, profile=profile)
    return out, ce.confirm_draft(store_db, out["token"], ledger_db_path=ledger_db_path)


# ═════════════════════════════════════════════════════════════════════════════
# validate_draft_fields — transfer-aware validation
# ═════════════════════════════════════════════════════════════════════════════


def test_validate_transfer_draft_ok(store_db, active_profile):
    assert ce.validate_draft_fields(_transfer_draft()) == []


def test_validate_transfer_draft_missing_accounts(store_db, active_profile):
    errors = ce.validate_draft_fields(_transfer_draft(from_account="", to_account=""))
    joined = "; ".join(errors)
    assert "asal" in joined
    assert "tujuan" in joined


def test_validate_transfer_draft_same_account(store_db, active_profile):
    errors = ce.validate_draft_fields(_transfer_draft(from_account="BCA", to_account="BCA"))
    assert any("tidak boleh sama" in e for e in errors)


def test_validate_transfer_draft_ignores_merchant(store_db, active_profile):
    """Transfers have no merchant, so the merchant checks must not fire."""
    draft = _transfer_draft(merchant_name="")
    assert ce.validate_draft_fields(draft) == []


def test_validate_expense_draft_unaffected(store_db, active_profile):
    errors = ce.validate_draft_fields(
        {
            "type": "expense",
            "total_amount": 50000,
            "merchant_name": "Warteg",
            "transaction_date": "2026-08-17",
        }
    )
    assert errors == []


# ═════════════════════════════════════════════════════════════════════════════
# confirm_draft -> double-entry transfer pair
# ═════════════════════════════════════════════════════════════════════════════


def test_confirm_transfer_creates_net_neutral_pair(store_db, ledger_db, active_profile, two_accounts):
    bca, jago = two_accounts
    out, res = _confirm(store_db, ledger_db, 111, _transfer_draft(), active_profile)

    pair = res["transaction"]
    assert pair["amount"] == 1_000_000.0
    assert pair["from_account_id"] == bca["id"]
    assert pair["to_account_id"] == jago["id"]
    assert pair["source"] == "telegram"

    transfers = ledger.list_transfers(ledger_db)
    assert len(transfers) == 1
    assert transfers[0]["pair_key"] == ce._hash_token(out["token"])

    assert ledger.account_balance(ledger_db, bca["id"]) == 9_000_000
    assert ledger.account_balance(ledger_db, jago["id"]) == 1_000_000
    total = ledger.account_balance(ledger_db, bca["id"]) + ledger.account_balance(ledger_db, jago["id"])
    assert total == 10_000_000  # net-neutral


def test_confirm_transfer_resolves_accounts_fuzzy(store_db, ledger_db, active_profile, two_accounts):
    """Names are normalized: 'rekening BCA' and 'jago bank' resolve to the same ids."""
    _, res = _confirm(
        store_db,
        ledger_db,
        112,
        _transfer_draft(from_account="rekening BCA", to_account="jago bank"),
        active_profile,
    )
    assert res["transaction"]["from_account_id"] == two_accounts[0]["id"]
    assert res["transaction"]["to_account_id"] == two_accounts[1]["id"]


def test_confirm_transfer_by_account_ids(store_db, ledger_db, active_profile, two_accounts):
    bca, jago = two_accounts
    _, res = _confirm(
        store_db,
        ledger_db,
        113,
        _transfer_draft(from_account_id=bca["id"], to_account_id=jago["id"], from_account="", to_account=""),
        active_profile,
    )
    assert res["transaction"]["from_account_id"] == bca["id"]
    assert res["transaction"]["to_account_id"] == jago["id"]


def test_confirm_transfer_same_account_reverts_to_pending(store_db, ledger_db, active_profile, two_accounts):
    with pytest.raises(ce.ValidationError):
        _confirm(
            store_db,
            ledger_db,
            114,
            _transfer_draft(from_account="BCA", to_account="BCA"),
            active_profile,
        )
    assert len(ledger.list_transfers(ledger_db)) == 0


def test_confirm_transfer_unknown_account_reverts_to_pending(store_db, ledger_db, active_profile, two_accounts):
    with pytest.raises(ce.ValidationError, match="tidak ditemukan"):
        _confirm(
            store_db,
            ledger_db,
            115,
            _transfer_draft(to_account="Tidak Ada"),
            active_profile,
        )
    assert len(ledger.list_transfers(ledger_db)) == 0


def test_confirm_transfer_insufficient_funds_reverts_to_pending(store_db, ledger_db, active_profile, two_accounts):
    with pytest.raises(ledger.InsufficientFundsError):
        _confirm(
            store_db,
            ledger_db,
            116,
            _transfer_draft(amount=99_000_000),
            active_profile,
        )
    assert len(ledger.list_transfers(ledger_db)) == 0


def test_confirm_transfer_replay_is_blocked(store_db, ledger_db, active_profile, two_accounts):
    ce.bind_chat(store_db, 117, profile=active_profile)
    out = ce.create_draft(store_db, 117, _transfer_draft(), profile=active_profile)
    ce.confirm_draft(store_db, out["token"], ledger_db_path=ledger_db)
    with pytest.raises(ce.ConflictError):
        ce.confirm_draft(store_db, out["token"], ledger_db_path=ledger_db)
    assert len(ledger.list_transfers(ledger_db)) == 1


def test_confirm_transfer_negative_amount_rejected(store_db, ledger_db, active_profile, two_accounts):
    with pytest.raises(ce.ValidationError):
        _confirm(
            store_db,
            ledger_db,
            118,
            _transfer_draft(amount=-5000),
            active_profile,
        )
    assert len(ledger.list_transfers(ledger_db)) == 0
