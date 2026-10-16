"""
Persistent Telegram confirmation store (Phase 3)
=================================================
Replaces the in-memory PENDING_RECEIPTS dict used by telegram_bot.py /
telegram_poll.py with a durable draft -> confirm/cancel lifecycle backed by
PostgreSQL (canonical) via the `chat.db` bridge target (schema `public`).

Lifecycle:
  pending   -> created by draft ingestion (photo OCR or NL text parse)
  confirmed -> one-time token consumption; the draft is committed into the
               profile ledger through ledger_engine.record_transaction with
               idempotency_key = token_hash (replay-safe)
  cancelled -> user explicitly discarded the draft
  expired   -> sweep marks drafts whose expires_at (created_at + 24h) passed

Tokens are single-use: only the SHA-256 hash is stored; the raw token is
returned exactly once at creation time.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from packages.api.backend.finance import ledger_engine
from packages.core.infrastructure.config import Config
from packages.core.infrastructure.persistence.database import Database

logger = logging.getLogger("backend.finance.confirmations")

CONFIRMATION_TTL_HOURS = 24

STATUS_PENDING = "pending"
STATUS_CONFIRMED = "confirmed"
STATUS_CANCELLED = "cancelled"
STATUS_EXPIRED = "expired"
VALID_STATUSES = {STATUS_PENDING, STATUS_CONFIRMED, STATUS_CANCELLED, STATUS_EXPIRED}


# ══════════════════════════════════════════════════════════════════════════════
# § Errors
# ══════════════════════════════════════════════════════════════════════════════

class ConfirmationError(Exception):
    """Base class for confirmation store errors."""


class NotFoundError(ConfirmationError):
    """Token or chat binding does not exist."""


class ConflictError(ConfirmationError):
    """Confirmation is no longer pending (consumed/cancelled/expired)."""


class ValidationError(ConfirmationError):
    """Draft or binding payload is invalid."""


# ══════════════════════════════════════════════════════════════════════════════
# § Schema (SQLite fallback only; PostgreSQL DDL lives in migration 009)
# ══════════════════════════════════════════════════════════════════════════════

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chat_bindings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id       INTEGER UNIQUE NOT NULL,
    profile       TEXT NOT NULL,
    display_name  TEXT,
    created_at    TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_confirmations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id         INTEGER NOT NULL,
    profile         TEXT NOT NULL,
    token_hash      TEXT UNIQUE NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    draft_json      TEXT NOT NULL,
    edit_target     TEXT,
    message_id      INTEGER,
    idempotency_key TEXT UNIQUE,
    created_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    consumed_at     TEXT,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pc_chat_status ON pending_confirmations(chat_id, status);
CREATE INDEX IF NOT EXISTS idx_pc_status_expires ON pending_confirmations(status, expires_at);
"""


# ══════════════════════════════════════════════════════════════════════════════
# § Helpers
# ══════════════════════════════════════════════════════════════════════════════

def ensure_schema(db_path: str) -> None:
    """Idempotently create the store tables.

    On PostgreSQL targets the bridge skips DDL (migration 009 owns them);
    on SQLite they are created locally for hermetic tests.
    """
    Database.execute_script(db_path, SCHEMA_SQL)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=CONFIRMATION_TTL_HOURS)).isoformat()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _query(db_path: str, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    return Database.query(db_path, sql, params)


def _execute(db_path: str, sql: str, params: tuple = ()) -> int:
    return Database.execute(db_path, sql, params)


def _query_one(db_path: str, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    rows = _query(db_path, sql, params)
    return rows[0] if rows else None


def _normalize_draft(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return {}
    return dict(raw or {})


def _row_to_confirmation(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "chat_id": row["chat_id"],
        "profile": row["profile"],
        "status": row["status"],
        "draft": _normalize_draft(row.get("draft_json")),
        "edit_target": row.get("edit_target"),
        "message_id": row.get("message_id"),
        "created_at": str(row.get("created_at") or ""),
        "expires_at": str(row.get("expires_at") or ""),
        "consumed_at": str(row.get("consumed_at") or "") if row.get("consumed_at") else None,
        "idempotency_key": row.get("idempotency_key"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# § Draft validation (Phase 4 hardening)
# ══════════════════════════════════════════════════════════════════════════════

def validate_draft_fields(draft: Dict[str, Any]) -> List[str]:
    """Sanity-check a draft before it enters the store (no silent ledger failures).

    Returns a list of human-readable errors; empty list means the draft can be
    queued for confirmation. Used by the Telegram entry points (n8n webhook flow
    and the standalone poller) to reject garbage receipts up-front.
    """
    if not isinstance(draft, dict) or not draft:
        return ["Draft is empty"]
    errors: List[str] = []

    amount = draft.get("total_amount", draft.get("amount"))
    if amount in (None, ""):
        errors.append("Jumlah (total_amount/amount) tidak ada")
    else:
        try:
            amount_f = float(str(amount).replace(",", "."))
            if amount_f <= 0:
                errors.append("Jumlah harus lebih dari 0")
            elif amount_f > 1_000_000_000:
                errors.append("Jumlah terlalu besar (>1 Miliar)")
        except (TypeError, ValueError):
            errors.append("Jumlah tidak valid")

    tx_type = str(draft.get("type") or draft.get("transaction_type") or "expense").strip().lower()

    if tx_type == "transfer":
        from_ref = draft.get("from_account") or draft.get("from_account_id") or draft.get("from")
        to_ref = draft.get("to_account") or draft.get("to_account_id") or draft.get("to")
        if not from_ref or not str(from_ref).strip():
            errors.append("Rekening asal (from_account) tidak ada")
        if not to_ref or not str(to_ref).strip():
            errors.append("Rekening tujuan (to_account) tidak ada")
        if from_ref and to_ref and str(from_ref).strip().lower() == str(to_ref).strip().lower():
            errors.append("Rekening asal dan tujuan tidak boleh sama")
        return errors

    merchant = str(draft.get("merchant_name") or draft.get("merchant") or "").strip()
    if not merchant:
        errors.append("Nama merchant tidak ada")
    elif len(merchant) < 2:
        errors.append("Nama merchant terlalu pendek")

    return errors


# ══════════════════════════════════════════════════════════════════════════════
# § Chat bindings (per-chat auth)
# ══════════════════════════════════════════════════════════════════════════════

def bind_chat(
    db_path: str,
    chat_id: int,
    profile: Optional[str] = None,
    display_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Upsert the chat -> profile binding. Returns the binding row."""
    ensure_schema(db_path)
    profile = (profile or Config.get_active_profile() or "").strip()
    if not profile:
        raise ValidationError("Profile is required to bind a chat")
    now = _now()
    existing = _query_one(db_path, "SELECT id FROM chat_bindings WHERE chat_id = ?", (chat_id,))
    if existing:
        _execute(
            db_path,
            "UPDATE chat_bindings SET profile = ?, display_name = COALESCE(?, display_name), "
            "last_seen_at = ? WHERE chat_id = ?",
            (profile, display_name, now, chat_id),
        )
    else:
        _execute(
            db_path,
            "INSERT INTO chat_bindings (chat_id, profile, display_name, created_at, last_seen_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, profile, display_name, now, now),
        )
    return get_binding(db_path, chat_id)  # type: ignore[return-value]


def get_binding(db_path: str, chat_id: int) -> Optional[Dict[str, Any]]:
    ensure_schema(db_path)
    row = _query_one(
        db_path, "SELECT * FROM chat_bindings WHERE chat_id = ?", (chat_id,)
    )
    if not row:
        return None
    return {
        "chat_id": row["chat_id"],
        "profile": row["profile"],
        "display_name": row.get("display_name"),
        "created_at": str(row.get("created_at") or ""),
        "last_seen_at": str(row.get("last_seen_at") or ""),
    }


def list_bindings(db_path: str) -> List[Dict[str, Any]]:
    ensure_schema(db_path)
    rows = _query(db_path, "SELECT * FROM chat_bindings ORDER BY chat_id ASC")
    return [
        {
            "chat_id": r["chat_id"],
            "profile": r["profile"],
            "display_name": r.get("display_name"),
            "created_at": str(r.get("created_at") or ""),
            "last_seen_at": str(r.get("last_seen_at") or ""),
        }
        for r in rows
    ]


def require_binding(db_path: str, chat_id: int) -> Dict[str, Any]:
    """Per-chat auth gate: raises NotFoundError when the chat is unbound."""
    binding = get_binding(db_path, chat_id)
    if not binding:
        raise NotFoundError(f"Chat {chat_id} is not bound to any profile")
    return binding


# ══════════════════════════════════════════════════════════════════════════════
# § Drafts
# ══════════════════════════════════════════════════════════════════════════════

def create_draft(
    db_path: str,
    chat_id: int,
    draft: Dict[str, Any],
    *,
    profile: Optional[str] = None,
    token: Optional[str] = None,
    message_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Persist a pending confirmation. Returns the row + the single-use token."""
    ensure_schema(db_path)
    binding = require_binding(db_path, chat_id)
    resolved_profile = (profile or binding["profile"]).strip()
    if not isinstance(draft, dict) or not draft:
        raise ValidationError("Draft must be a non-empty object")

    raw_token = token or secrets.token_urlsafe(24)
    token_hash = _hash_token(raw_token)
    now = _now()
    _execute(
        db_path,
        "INSERT INTO pending_confirmations "
        "(chat_id, profile, token_hash, status, draft_json, message_id, idempotency_key, "
        " created_at, expires_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            chat_id,
            resolved_profile,
            token_hash,
            STATUS_PENDING,
            json.dumps(draft, ensure_ascii=False),
            message_id,
            token_hash,
            now,
            _expiry(),
            now,
        ),
    )
    row = _query_one(
        db_path, "SELECT * FROM pending_confirmations WHERE token_hash = ?", (token_hash,)
    )
    if row is None:  # pragma: no cover - should never happen
        raise ConfirmationError("Failed to create confirmation")
    out = _row_to_confirmation(row)
    out["token"] = raw_token
    return out


def get_draft(db_path: str, token: str) -> Dict[str, Any]:
    """Fetch a confirmation by its raw token. Raises NotFoundError when unknown."""
    ensure_schema(db_path)
    row = _query_one(
        db_path,
        "SELECT * FROM pending_confirmations WHERE token_hash = ?",
        (_hash_token(token),),
    )
    if not row:
        raise NotFoundError("Confirmation not found")
    return _row_to_confirmation(row)


def list_drafts(
    db_path: str,
    chat_id: int,
    status: str = STATUS_PENDING,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List confirmations for a chat, oldest first by default."""
    ensure_schema(db_path)
    rows = _query(
        db_path,
        "SELECT * FROM pending_confirmations WHERE chat_id = ? AND status = ? "
        "ORDER BY id ASC LIMIT ?",
        (chat_id, status, limit),
    )
    return [_row_to_confirmation(r) for r in rows]


def list_all_drafts(db_path: str, chat_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    ensure_schema(db_path)
    rows = _query(
        db_path,
        "SELECT * FROM pending_confirmations WHERE chat_id = ? "
        "ORDER BY id DESC LIMIT ?",
        (chat_id, limit),
    )
    return [_row_to_confirmation(r) for r in rows]


def update_draft(
    db_path: str,
    token: str,
    *,
    draft: Optional[Dict[str, Any]] = None,
    edit_target: Optional[str] = None,
    message_id: Optional[int] = None,
) -> Dict[str, Any]:
    """In-place edit of a still-pending draft. Raises ConflictError otherwise."""
    row = get_draft(db_path, token)
    if row["status"] != STATUS_PENDING:
        raise ConflictError(f"Confirmation is already {row['status']}")

    sets: List[str] = []
    params: List[Any] = []
    if draft is not None:
        sets.append("draft_json = ?")
        params.append(json.dumps(draft, ensure_ascii=False))
    if edit_target is not None:
        sets.append("edit_target = ?")
        params.append(edit_target or None)
    if message_id is not None:
        sets.append("message_id = ?")
        params.append(message_id)
    sets.append("updated_at = ?")
    params.append(_now())
    params.append(row["id"])
    _execute(db_path, f"UPDATE pending_confirmations SET {', '.join(sets)} WHERE id = ?", tuple(params))
    return get_draft(db_path, token)


def _consume(db_path: str, row_id: int) -> bool:
    """Atomically flip pending -> confirmed. Returns True when this caller won."""
    affected = _execute(
        db_path,
        "UPDATE pending_confirmations SET status = ?, consumed_at = ?, updated_at = ? "
        "WHERE id = ? AND status = ? AND expires_at > ?",
        (STATUS_CONFIRMED, _now(), _now(), row_id, STATUS_PENDING, _now()),
    )
    return bool(affected)


def confirm_draft(
    db_path: str,
    token: str,
    *,
    ledger_db_path: str,
) -> Dict[str, Any]:
    """Consume a pending confirmation and commit it into the profile ledger.

    The commit is replay-safe: `record_transaction` is called with
    idempotency_key = token_hash, so retries after partial failure return the
    already-inserted transaction instead of duplicating it.
    """
    row = get_draft(db_path, token)
    if row["status"] != STATUS_PENDING:
        raise ConflictError(f"Confirmation is already {row['status']}")

    expires_at = row["expires_at"]
    if expires_at and expires_at <= _now():
        _execute(
            db_path,
            "UPDATE pending_confirmations SET status = ?, updated_at = ? WHERE id = ?",
            (STATUS_EXPIRED, _now(), row["id"]),
        )
        raise ConflictError("Confirmation has expired (24h TTL)")

    active_profile = Config.get_active_profile()
    if row["profile"] != active_profile:
        raise ConflictError(
            f"Draft belongs to profile '{row['profile']}', but '{active_profile}' is active. "
            "Switch profile before confirming."
        )

    if not _consume(db_path, row["id"]):
        # Race: another consumer already took it or it expired mid-flight.
        refreshed = get_draft(db_path, token)
        raise ConflictError(f"Confirmation is already {refreshed['status']}")

    try:
        transaction = _commit_to_ledger(ledger_db_path, row["draft"], row["idempotency_key"])
    except Exception:
        logger.exception("Ledger commit failed; reverting confirmation to pending")
        _execute(
            db_path,
            "UPDATE pending_confirmations SET status = ?, consumed_at = NULL, updated_at = ? "
            "WHERE id = ? AND status = ?",
            (STATUS_PENDING, _now(), row["id"], STATUS_CONFIRMED),
        )
        raise

    confirmed = get_draft(db_path, token)
    return {"confirmation": confirmed, "transaction": transaction}


def _normalize_account_name(name: Any) -> str:
    """Canonical key for account-name matching: lowercase, no punctuation/stopwords."""
    if name is None:
        return ""
    n = str(name).lower().strip()
    n = re.sub(r"[^\w\s]", " ", n)
    for w in ("rekening", "kartu", "akun", "dompet", "e-wallet", "ewallet",
              "dari", "ke", "kepada", "from", "to", "account", "bank"):
        n = n.replace(w, " ")
    return " ".join(n.split())


def resolve_account_ref(ledger_db_path: str, ref: Any) -> int:
    """Resolve an account reference (numeric id or display name) to its ledger id.

    Name resolution is tolerant: normalized exact match first, then substring
    containment in both directions. Raises ValidationError when no account
    matches so the user gets a clear, actionable message.
    """
    raw = str(ref or "").strip()
    if not raw:
        raise ValidationError("Account reference is required")
    if raw.isdigit():
        acc = ledger_engine.get_account(ledger_db_path, int(raw))
        if acc:
            return acc["id"]

    norm = _normalize_account_name(raw)
    if not norm:
        raise ValidationError(f"Account reference {ref!r} is invalid")

    accounts = ledger_engine.list_accounts(ledger_db_path, include_inactive=True)
    for acc in accounts:
        if _normalize_account_name(acc["name"]) == norm:
            return acc["id"]
    for acc in accounts:
        acc_norm = _normalize_account_name(acc["name"])
        if acc_norm and (norm in acc_norm or acc_norm in norm):
            return acc["id"]
    raise ValidationError(
        f"Rekening {ref!r} tidak ditemukan di ledger. Buat rekening dulu "
        "(CLI/API) atau ketik ulang nama rekeningnya."
    )


def _commit_transfer_to_ledger(
    ledger_db_path: str,
    draft: Dict[str, Any],
    idempotency_key: Optional[str],
) -> Dict[str, Any]:
    """Commit a transfer draft as a double-entry transfer pair (net-neutral)."""
    amount = draft.get("amount")
    if amount is None:
        amount = draft.get("total_amount")
    if amount is None:
        raise ValidationError("Draft is missing an amount")
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        raise ValidationError(f"Invalid transfer amount: {amount!r}")
    if amount_f <= 0:
        raise ValidationError("Transfer amount must be greater than 0")

    from_id = resolve_account_ref(
        ledger_db_path, draft.get("from_account") or draft.get("from_account_id") or draft.get("from")
    )
    to_id = resolve_account_ref(
        ledger_db_path, draft.get("to_account") or draft.get("to_account_id") or draft.get("to")
    )
    if from_id == to_id:
        raise ValidationError("Transfer source and destination must differ")

    tx_date = draft.get("date") or draft.get("tx_date") or draft.get("transaction_date")
    if not tx_date:
        tx_date = datetime.now(timezone.utc).date().isoformat()

    description = str(
        draft.get("description") or draft.get("notes") or "Transfer"
    ).strip()
    confidence = draft.get("confidence")

    return ledger_engine.record_transfer(
        ledger_db_path,
        from_account_id=from_id,
        to_account_id=to_id,
        amount=amount_f,
        tx_date=tx_date,
        description=description,
        source="telegram",
        confidence=float(confidence) if confidence is not None else None,
        pair_key=idempotency_key,
        check_balance=True,
    )


def _commit_to_ledger(
    ledger_db_path: str,
    draft: Dict[str, Any],
    idempotency_key: Optional[str],
) -> Dict[str, Any]:
    ledger_engine.ensure_schema(ledger_db_path)

    ttype = str(draft.get("type") or draft.get("transaction_type") or "expense").strip().lower()
    if ttype == ledger_engine.TRANSFER_TYPE:
        return _commit_transfer_to_ledger(ledger_db_path, draft, idempotency_key)
    if ttype not in ledger_engine.SUPPORTED_TYPES:
        raise ValidationError(f"Unsupported transaction type {ttype!r}")

    amount = draft.get("amount")
    if amount is None:
        amount = draft.get("total_amount")
    if amount is None:
        raise ValidationError("Draft is missing an amount")

    merchant_name = str(draft.get("merchant_name") or draft.get("merchant") or "").strip()
    description = str(
        draft.get("description")
        or draft.get("notes")
        or merchant_name
        or (draft.get("source") if draft.get("source") else "")
    ).strip()

    category_name = str(draft.get("category") or "").strip()
    if not category_name or category_name.lower() == "other":
        category_name = "Other"
    kind = "expense" if ttype == "expense" else "income"
    category_id = None
    try:
        category_id = ledger_engine._get_or_create_category(
            ledger_db_path, category_name, kind
        )["id"]
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Category resolution failed for {category_name!r}: {exc}")

    merchant_id = None
    if merchant_name:
        try:
            merchant_id = ledger_engine.remember_merchant(
                ledger_db_path, merchant_name, category=category_name if category_id else None
            )["id"]
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Merchant resolution failed for {merchant_name!r}: {exc}")

    account_id = draft.get("account_id")
    if account_id is not None:
        account = ledger_engine.get_account(ledger_db_path, account_id)
        if not account:
            account_id = None
    if account_id is None:
        accounts = ledger_engine.list_accounts(ledger_db_path)
        if accounts:
            account_id = accounts[0]["id"]
        else:
            account_id = ledger_engine.create_account(
                ledger_db_path,
                name=ledger_engine._DEFAULT_ACCOUNT_NAME,
                account_type="bank",
                currency="IDR",
                opening_balance=0.0,
                is_default=True,
            )["id"]

    tx_date = draft.get("date") or draft.get("tx_date") or draft.get("transaction_date")
    if not tx_date:
        tx_date = datetime.now(timezone.utc).date().isoformat()
    confidence = draft.get("confidence")

    return ledger_engine.record_transaction(
        ledger_db_path,
        ttype=ttype,
        amount=float(amount),
        tx_date=tx_date,
        account_id=account_id,
        merchant_id=merchant_id,
        category_id=category_id,
        category=category_name,
        description=description,
        source="telegram",
        confidence=float(confidence) if confidence is not None else None,
        idempotency_key=idempotency_key,
    )


def cancel_draft(db_path: str, token: str) -> Dict[str, Any]:
    """Cancel a still-pending confirmation."""
    row = get_draft(db_path, token)
    if row["status"] != STATUS_PENDING:
        raise ConflictError(f"Confirmation is already {row['status']}")
    _execute(
        db_path,
        "UPDATE pending_confirmations SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
        (STATUS_CANCELLED, _now(), row["id"], STATUS_PENDING),
    )
    return get_draft(db_path, token)


def cancel_all_pending(db_path: str, chat_id: int) -> int:
    """Cancel every pending confirmation for a chat. Returns the count."""
    ensure_schema(db_path)
    return _execute(
        db_path,
        "UPDATE pending_confirmations SET status = ?, updated_at = ? "
        "WHERE chat_id = ? AND status = ?",
        (STATUS_CANCELLED, _now(), chat_id, STATUS_PENDING),
    )


def expire_stale(db_path: str) -> int:
    """Sweep expired pending confirmations. Returns the number expired."""
    ensure_schema(db_path)
    return _execute(
        db_path,
        "UPDATE pending_confirmations SET status = ?, updated_at = ? "
        "WHERE status = ? AND expires_at <= ?",
        (STATUS_EXPIRED, _now(), STATUS_PENDING, _now()),
    )
