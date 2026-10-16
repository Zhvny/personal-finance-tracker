"""
ledger_engine.py — Unified Transaction & Account Engine (Phase 2)
=================================================================
Single source of truth for the canonical per-profile ledger:

    accounts        → bank / e-wallet / cash / investment / other buckets
    categories      → controlled expense / income category registry
    merchants       → normalized merchant registry (per profile)
    transactions    → unified ledger (type/source/confidence/idempotency_key)
    transfer_pairs  → double-entry pairing of the two transfer legs

All persistence flows through packages.core.infrastructure.persistence.database
(Database bridge): SQLite when the db_path is a local file, PostgreSQL per-profile
schema when the path maps to a canonical target (e.g. finance.db). SQL uses '?'
placeholders everywhere so the bridge can translate to '%s' on Postgres.

Invariants guarded here (matching docs/AUDIT_2026-08-16.md Phase 2):
  - zero / negative amounts are rejected
  - huge amounts are bounded by DECIMAL(15, 2)
  - transfers are double-entry and net-neutral by construction
  - idempotency_key provides duplicate protection for replay-safe writes
  - deleting a transfer leg directly is forbidden (use delete_transfer)
"""

from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from packages.core.infrastructure.persistence.database import Database

logger = logging.getLogger("backend.finance.ledger")


# ══════════════════════════════════════════════════════════════════════════════
# § Errors
# ══════════════════════════════════════════════════════════════════════════════

class LedgerError(Exception):
    """Base class for all ledger engine errors."""


class ValidationError(LedgerError):
    """Input violates a ledger invariant (zero/negative amount, bad type...)."""


class NotFoundError(LedgerError):
    """Referenced account / category / merchant / transaction does not exist."""


class DuplicateError(LedgerError):
    """A unique field already exists (account name, idempotency key...)."""


class ConflictError(LedgerError):
    """Operation conflicts with ledger invariants (delete in use, transfer leg...)."""


class InsufficientFundsError(LedgerError):
    """Transfer would leave the source account with a negative balance."""


# ══════════════════════════════════════════════════════════════════════════════
# § Constants
# ══════════════════════════════════════════════════════════════════════════════

ACCOUNT_TYPES = {"bank", "e-wallet", "cash", "investment", "other"}
CATEGORY_KINDS = {"expense", "income", "transfer", "investment", "other"}
# Single-entry transaction types supported by record_transaction().
# 'transfer' and 'adjustment' are reserved for record_transfer() / future use.
SUPPORTED_TYPES = {"expense", "income", "investment"}
TRANSFER_TYPE = "transfer"
MAX_AMOUNT = Decimal("9999999999999.99")  # DECIMAL(15, 2) upper bound

DEFAULT_CATEGORIES = [
    ("Food", "expense"), ("Transport", "expense"), ("Housing", "expense"),
    ("Entertainment", "expense"), ("Health", "expense"), ("Shopping", "expense"),
    ("Education", "expense"), ("Investment", "expense"), ("Other", "expense"),
    ("Salary", "income"), ("Bonus", "income"), ("Gift", "income"), ("Other", "income"),
]

_DEFAULT_ACCOUNT_NAME = "Default"
_MERCHANT_BRANCH_RE = re.compile(
    r"\s*[#\-–]\s*\w+$|"          # " #12" / " - CBD"
    r"\s+\d+$|"                   # " 02"
    r"\s*\(.*?\)$|"               # " (JKT)"
    r"\s*\bno\.?\s*\d+$",         # " No. 5"
    re.IGNORECASE,
)

# ══════════════════════════════════════════════════════════════════════════════
# § Schema
# ══════════════════════════════════════════════════════════════════════════════

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'bank'
        CHECK (type IN ('bank', 'e-wallet', 'cash', 'investment', 'other')),
    currency TEXT NOT NULL DEFAULT 'IDR',
    opening_balance DECIMAL(15, 2) NOT NULL DEFAULT 0,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'expense'
        CHECK (kind IN ('expense', 'income', 'transfer', 'investment', 'other')),
    color TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name, kind)
);

CREATE TABLE IF NOT EXISTS merchants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    display_name TEXT,
    category_id INTEGER REFERENCES categories(id),
    category TEXT,
    edit_count INTEGER NOT NULL DEFAULT 1,
    last_seen DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK (type IN ('expense', 'income', 'transfer', 'investment', 'adjustment')),
    amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'IDR',
    account_id INTEGER REFERENCES accounts(id),
    merchant_id INTEGER REFERENCES merchants(id),
    category_id INTEGER REFERENCES categories(id),
    category TEXT,
    description TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    confidence DECIMAL(5, 4),
    idempotency_key TEXT UNIQUE,
    tx_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(tx_date);
CREATE INDEX IF NOT EXISTS idx_tx_account ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_tx_type ON transactions(type);

CREATE TABLE IF NOT EXISTS transfer_pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_transaction_id INTEGER NOT NULL UNIQUE REFERENCES transactions(id),
    to_transaction_id INTEGER NOT NULL UNIQUE REFERENCES transactions(id),
    amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0),
    pair_key TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tp_from ON transfer_pairs(from_transaction_id);
CREATE INDEX IF NOT EXISTS idx_tp_to ON transfer_pairs(to_transaction_id);
"""


def ensure_schema(db_path: str) -> None:
    """Idempotently create the ledger tables.

    On PostgreSQL targets the bridge skips DDL (tables are managed by the
    migration system / SchemaInitializer); on SQLite it creates them locally.
    """
    Database.execute_script(db_path, SCHEMA_SQL)


def seed_defaults(db_path: str) -> None:
    """Idempotently seed the default account and category registry."""
    ensure_schema(db_path)
    if not list_accounts(db_path):
        create_account(
            db_path,
            name=_DEFAULT_ACCOUNT_NAME,
            account_type="bank",
            currency="IDR",
            opening_balance=0.0,
            is_default=True,
        )
    for cat_name, cat_kind in DEFAULT_CATEGORIES:
        _get_or_create_category(db_path, cat_name, cat_kind)


# ══════════════════════════════════════════════════════════════════════════════
# § Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        raise ValidationError("Date is required")
    if text.startswith(("'", '"')) and text.endswith(("'", '"')):
        text = text[1:-1]
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text).date()
    except ValueError as exc:
        raise ValidationError(f"Invalid date format: {text!r}") from exc


def _to_amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"Invalid amount: {value!r}") from exc
    if amount <= 0:
        raise ValidationError("Amount must be greater than 0")
    if amount > MAX_AMOUNT:
        raise ValidationError(f"Amount exceeds maximum supported value ({MAX_AMOUNT})")
    return amount.quantize(Decimal("0.01"))


def _normalize_merchant(name: str) -> str:
    if not name:
        return ""
    cleaned = _MERCHANT_BRANCH_RE.sub("", name.strip())
    return re.sub(r"\s+", " ", cleaned).lower().strip()


def _as_amount(value: Any) -> float:
    if value is None:
        return 0.0
    return round(float(Decimal(str(value))), 2)


def _query(db_path: str, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    return Database.query(db_path, sql, params)


def _execute(db_path: str, sql: str, params: tuple = ()) -> int:
    return Database.execute(db_path, sql, params)


def _is_postgres_target(db_path: str) -> bool:
    """True when the db_path maps to a canonical PostgreSQL profile schema."""
    return Database._is_postgres_target(db_path)


def _query_one(db_path: str, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    rows = _query(db_path, sql, params)
    return rows[0] if rows else None


def _tx_exists(db_path: str, idempotency_key: str) -> bool:
    return (
        _query_one(
            db_path,
            "SELECT id FROM transactions WHERE idempotency_key = ?",
            (idempotency_key,),
        )
        is not None
    )


# ══════════════════════════════════════════════════════════════════════════════
# § Accounts
# ══════════════════════════════════════════════════════════════════════════════

def create_account(
    db_path: str,
    name: str,
    account_type: str = "bank",
    currency: str = "IDR",
    opening_balance: float = 0.0,
    is_default: bool = False,
) -> Dict[str, Any]:
    ensure_schema(db_path)
    name = (name or "").strip()
    if not name:
        raise ValidationError("Account name cannot be empty")
    if account_type not in ACCOUNT_TYPES:
        raise ValidationError(
            f"Invalid account type {account_type!r}; allowed: {sorted(ACCOUNT_TYPES)}"
        )
    if _query_one(db_path, "SELECT id FROM accounts WHERE name = ?", (name,)):
        raise DuplicateError(f"Account already exists: {name}")

    try:
        opening = Decimal(str(opening_balance or 0)).quantize(Decimal("0.01"))
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"Invalid opening balance: {opening_balance!r}") from exc
    if abs(opening) > MAX_AMOUNT:
        raise ValidationError(f"Opening balance exceeds maximum supported value ({MAX_AMOUNT})")

    _execute(
        db_path,
        "INSERT INTO accounts (name, type, currency, opening_balance, is_default, is_active) "
        "VALUES (?, ?, ?, ?, ?, TRUE)",
        (name, account_type, currency, float(opening), is_default),
    )
    row = _query_one(db_path, "SELECT * FROM accounts WHERE name = ?", (name,))
    if row is None:  # pragma: no cover - should never happen
        raise LedgerError("Account insert failed")
    return _account_out(row)


def _account_out(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "currency": row["currency"],
        "opening_balance": _as_amount(row["opening_balance"]),
        "is_default": bool(row["is_default"]),
        "is_active": bool(row["is_active"]),
        "created_at": str(row.get("created_at") or ""),
    }


def get_account(db_path: str, account_id: int) -> Optional[Dict[str, Any]]:
    row = _query_one(db_path, "SELECT * FROM accounts WHERE id = ?", (account_id,))
    return _account_out(row) if row else None


def list_accounts(db_path: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM accounts"
    params: tuple = ()
    if not include_inactive:
        sql += " WHERE is_active = TRUE"
    sql += " ORDER BY is_default DESC, id ASC"
    return [_account_out(r) for r in _query(db_path, sql, params)]


def update_account(db_path: str, account_id: int, **fields: Any) -> Dict[str, Any]:
    if not get_account(db_path, account_id):
        raise NotFoundError(f"Account not found: {account_id}")

    allowed = {"name", "type", "currency", "opening_balance", "is_default", "is_active"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValidationError(f"Unknown account field(s): {sorted(unknown)}")

    sets: List[str] = []
    params: List[Any] = []
    if "name" in fields:
        name = (fields["name"] or "").strip()
        if not name:
            raise ValidationError("Account name cannot be empty")
        if _query_one(
            db_path, "SELECT id FROM accounts WHERE name = ? AND id != ?", (name, account_id)
        ):
            raise DuplicateError(f"Account already exists: {name}")
        sets.append("name = ?")
        params.append(name)
    if "type" in fields:
        if fields["type"] not in ACCOUNT_TYPES:
            raise ValidationError(f"Invalid account type: {fields['type']!r}")
        sets.append("type = ?")
        params.append(fields["type"])
    if "currency" in fields:
        currency = (fields["currency"] or "").strip()
        if not currency:
            raise ValidationError("Currency cannot be empty")
        sets.append("currency = ?")
        params.append(currency)
    if "opening_balance" in fields:
        try:
            opening = Decimal(str(fields["opening_balance"])).quantize(Decimal("0.01"))
        except Exception as exc:  # noqa: BLE001
            raise ValidationError(f"Invalid opening balance: {fields['opening_balance']!r}") from exc
        if abs(opening) > MAX_AMOUNT:
            raise ValidationError("Opening balance exceeds maximum supported value")
        sets.append("opening_balance = ?")
        params.append(float(opening))
    if "is_default" in fields:
        sets.append("is_default = ?")
        params.append(bool(fields["is_default"]))
    if "is_active" in fields:
        sets.append("is_active = ?")
        params.append(bool(fields["is_active"]))

    if not sets:
        return get_account(db_path, account_id)  # type: ignore[return-value]

    params.append(account_id)
    _execute(db_path, f"UPDATE accounts SET {', '.join(sets)} WHERE id = ?", tuple(params))
    return get_account(db_path, account_id)  # type: ignore[return-value]


def delete_account(db_path: str, account_id: int) -> bool:
    if not get_account(db_path, account_id):
        raise NotFoundError(f"Account not found: {account_id}")
    referenced = _query_one(
        db_path,
        "SELECT id FROM transactions WHERE account_id = ? LIMIT 1",
        (account_id,),
    )
    if referenced:
        raise ConflictError("Account has transactions; reassign or delete them first")
    _execute(db_path, "DELETE FROM accounts WHERE id = ?", (account_id,))
    return True


def account_balance(db_path: str, account_id: int, as_of: Optional[date] = None) -> float:
    """Compute an account balance including opening balance and all inflows/outflows.

    Transfers are direction-aware via transfer_pairs, so they never distort a
    single account's balance and are globally net-neutral.
    """
    if not get_account(db_path, account_id):
        raise NotFoundError(f"Account not found: {account_id}")
    cutoff = (_parse_date(as_of) if as_of else date.max).isoformat()
    sql = """
        SELECT
            a.opening_balance AS opening_balance,
            COALESCE((SELECT SUM(t.amount) FROM transactions t
                       WHERE t.account_id = a.id AND t.type = 'income' AND t.tx_date <= ?), 0) AS inflow,
            COALESCE((SELECT SUM(t.amount) FROM transactions t
                       WHERE t.account_id = a.id AND t.type IN ('expense', 'investment') AND t.tx_date <= ?), 0) AS outflow,
            COALESCE((SELECT SUM(tp.amount) FROM transfer_pairs tp
                       JOIN transactions t ON t.id = tp.to_transaction_id
                       WHERE t.account_id = a.id AND t.tx_date <= ?), 0) AS transfer_in,
            COALESCE((SELECT SUM(tp.amount) FROM transfer_pairs tp
                       JOIN transactions t ON t.id = tp.from_transaction_id
                       WHERE t.account_id = a.id AND t.tx_date <= ?), 0) AS transfer_out
        FROM accounts a
        WHERE a.id = ?
    """
    row = _query_one(
        db_path, sql, (cutoff, cutoff, cutoff, cutoff, account_id)
    )
    if row is None:
        raise NotFoundError(f"Account not found: {account_id}")
    return round(
        _as_amount(row["opening_balance"])
        + _as_amount(row["inflow"])
        - _as_amount(row["outflow"])
        + _as_amount(row["transfer_in"])
        - _as_amount(row["transfer_out"]),
        2,
    )


# ══════════════════════════════════════════════════════════════════════════════
# § Categories
# ══════════════════════════════════════════════════════════════════════════════

def _category_out(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "kind": row["kind"],
        "color": row.get("color"),
        "created_at": str(row.get("created_at") or ""),
    }


def create_category(
    db_path: str, name: str, kind: str = "expense", color: Optional[str] = None
) -> Dict[str, Any]:
    ensure_schema(db_path)
    name = (name or "").strip()
    if not name:
        raise ValidationError("Category name cannot be empty")
    if kind not in CATEGORY_KINDS:
        raise ValidationError(f"Invalid category kind {kind!r}; allowed: {sorted(CATEGORY_KINDS)}")
    existing = _query_one(
        db_path, "SELECT id FROM categories WHERE name = ? AND kind = ?", (name, kind)
    )
    if existing:
        raise DuplicateError(f"Category already exists: {name}/{kind}")
    _execute(
        db_path,
        "INSERT INTO categories (name, kind, color) VALUES (?, ?, ?)",
        (name, kind, color),
    )
    row = _query_one(db_path, "SELECT * FROM categories WHERE name = ? AND kind = ?", (name, kind))
    return _category_out(row)  # type: ignore[arg-type]


def get_category(db_path: str, category_id: int) -> Optional[Dict[str, Any]]:
    row = _query_one(db_path, "SELECT * FROM categories WHERE id = ?", (category_id,))
    return _category_out(row) if row else None


def list_categories(db_path: str, kind: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM categories"
    params: tuple = ()
    if kind:
        sql += " WHERE kind = ?"
        params = (kind,)
    sql += " ORDER BY kind ASC, name ASC"
    return [_category_out(r) for r in _query(db_path, sql, params)]


def update_category(
    db_path: str, category_id: int, name: Optional[str] = None, color: Optional[str] = None
) -> Dict[str, Any]:
    if not get_category(db_path, category_id):
        raise NotFoundError(f"Category not found: {category_id}")
    sets: List[str] = []
    params: List[Any] = []
    if name is not None:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Category name cannot be empty")
        sets.append("name = ?")
        params.append(name)
    if color is not None:
        sets.append("color = ?")
        params.append(color)
    if not sets:
        return get_category(db_path, category_id)  # type: ignore[return-value]
    params.append(category_id)
    _execute(db_path, f"UPDATE categories SET {', '.join(sets)} WHERE id = ?", tuple(params))
    return get_category(db_path, category_id)  # type: ignore[return-value]


def delete_category(db_path: str, category_id: int) -> bool:
    if not get_category(db_path, category_id):
        raise NotFoundError(f"Category not found: {category_id}")
    if _query_one(
        db_path, "SELECT id FROM transactions WHERE category_id = ? LIMIT 1", (category_id,)
    ):
        raise ConflictError("Category is referenced by transactions")
    if _query_one(
        db_path, "SELECT id FROM merchants WHERE category_id = ? LIMIT 1", (category_id,)
    ):
        raise ConflictError("Category is referenced by merchants")
    _execute(db_path, "DELETE FROM categories WHERE id = ?", (category_id,))
    return True


def _get_or_create_category(db_path: str, name: str, kind: str = "expense") -> Dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValidationError("Category name cannot be empty")
    row = _query_one(db_path, "SELECT * FROM categories WHERE name = ? AND kind = ?", (name, kind))
    if row:
        return _category_out(row)
    _execute(db_path, "INSERT INTO categories (name, kind) VALUES (?, ?)", (name, kind))
    row = _query_one(db_path, "SELECT * FROM categories WHERE name = ? AND kind = ?", (name, kind))
    return _category_out(row)  # type: ignore[arg-type]


# ══════════════════════════════════════════════════════════════════════════════
# § Merchants
# ══════════════════════════════════════════════════════════════════════════════

def _merchant_out(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "display_name": row.get("display_name"),
        "category_id": row.get("category_id"),
        "category": row.get("category"),
        "edit_count": row["edit_count"],
        "last_seen": str(row.get("last_seen") or ""),
        "created_at": str(row.get("created_at") or ""),
    }


def remember_merchant(
    db_path: str,
    name: str,
    category: Optional[str] = None,
    category_id: Optional[int] = None,
    display_name: Optional[str] = None,
    last_seen: Optional[date] = None,
) -> Dict[str, Any]:
    ensure_schema(db_path)
    norm = _normalize_merchant(name)
    if not norm:
        raise ValidationError("Merchant name cannot be empty")

    resolved_category: Optional[str] = category
    if category and not category_id:
        category_id = _get_or_create_category(db_path, category, "expense")["id"]
    if category_id:
        cat = get_category(db_path, category_id)
        if not cat:
            raise NotFoundError(f"Category not found: {category_id}")
        resolved_category = cat["name"]

    seen = last_seen or date.today()
    _execute(
        db_path,
        """
        INSERT INTO merchants (name, display_name, category_id, category, edit_count, last_seen)
        VALUES (?, ?, ?, ?, 1, ?)
        ON CONFLICT (name) DO UPDATE SET
            category_id = COALESCE(excluded.category_id, merchants.category_id),
            category = COALESCE(excluded.category, merchants.category),
            display_name = COALESCE(excluded.display_name, merchants.display_name),
            last_seen = excluded.last_seen,
            edit_count = merchants.edit_count + 1
        """,
        (norm, display_name or norm, category_id, resolved_category, seen.isoformat()),
    )
    row = _query_one(db_path, "SELECT * FROM merchants WHERE name = ?", (norm,))
    return _merchant_out(row)  # type: ignore[arg-type]


def lookup_merchant(db_path: str, name: str) -> Optional[Dict[str, Any]]:
    norm = _normalize_merchant(name)
    if not norm:
        return None
    row = _query_one(db_path, "SELECT * FROM merchants WHERE name = ?", (norm,))
    return _merchant_out(row) if row else None


def list_merchants(db_path: str, limit: int = 200) -> List[Dict[str, Any]]:
    rows = _query(
        db_path,
        "SELECT * FROM merchants ORDER BY edit_count DESC, last_seen DESC LIMIT ?",
        (limit,),
    )
    return [_merchant_out(r) for r in rows]


def forget_merchant(db_path: str, merchant_id: int) -> bool:
    if not _query_one(db_path, "SELECT id FROM merchants WHERE id = ?", (merchant_id,)):
        raise NotFoundError(f"Merchant not found: {merchant_id}")
    if _query_one(
        db_path, "SELECT id FROM transactions WHERE merchant_id = ? LIMIT 1", (merchant_id,)
    ):
        raise ConflictError("Merchant is referenced by transactions")
    _execute(db_path, "DELETE FROM merchants WHERE id = ?", (merchant_id,))
    return True


# ══════════════════════════════════════════════════════════════════════════════
# § Transactions
# ══════════════════════════════════════════════════════════════════════════════

def _tx_out(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "type": row["type"],
        "amount": _as_amount(row["amount"]),
        "currency": row["currency"],
        "account_id": row.get("account_id"),
        "account_name": row.get("account_name"),
        "merchant_id": row.get("merchant_id"),
        "merchant_name": row.get("merchant_name"),
        "category_id": row.get("category_id"),
        "category": row.get("category"),
        "category_name": row.get("category_name"),
        "description": row.get("description"),
        "source": row.get("source"),
        "confidence": row.get("confidence"),
        "idempotency_key": row.get("idempotency_key"),
        "tx_date": str(row.get("tx_date")),
        "created_at": str(row.get("created_at") or ""),
    }


_TX_SELECT = """
    SELECT t.*,
           a.name AS account_name,
           m.name AS merchant_name,
           c.name AS category_name
    FROM transactions t
    LEFT JOIN accounts a ON a.id = t.account_id
    LEFT JOIN merchants m ON m.id = t.merchant_id
    LEFT JOIN categories c ON c.id = t.category_id
"""


def _validate_relations(
    db_path: str,
    account_id: Optional[int],
    merchant_id: Optional[int],
    category_id: Optional[int],
) -> None:
    if account_id is not None:
        if not get_account(db_path, account_id):
            raise NotFoundError(f"Account not found: {account_id}")
    if merchant_id is not None:
        if not _query_one(db_path, "SELECT id FROM merchants WHERE id = ?", (merchant_id,)):
            raise NotFoundError(f"Merchant not found: {merchant_id}")
    if category_id is not None:
        if not get_category(db_path, category_id):
            raise NotFoundError(f"Category not found: {category_id}")


def record_transaction(
    db_path: str,
    *,
    ttype: str,
    amount: float,
    tx_date: Any,
    account_id: Optional[int] = None,
    merchant_id: Optional[int] = None,
    category_id: Optional[int] = None,
    category: Optional[str] = None,
    description: Optional[str] = None,
    source: str = "manual",
    confidence: Optional[float] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_schema(db_path)
    if ttype not in SUPPORTED_TYPES:
        raise ValidationError(
            f"Unsupported transaction type {ttype!r}; allowed: {sorted(SUPPORTED_TYPES)}"
        )
    amount_dec = _to_amount(amount)
    tx = _parse_date(tx_date)
    today = date.today()
    if tx > today:
        raise ValidationError("Date cannot be in the future")
    _validate_relations(db_path, account_id, merchant_id, category_id)

    key = (idempotency_key or "").strip() or f"manual:{uuid.uuid4().hex}"
    existing = _query_one(
        db_path, "SELECT id FROM transactions WHERE idempotency_key = ?", (key,)
    )
    if existing:
        row = _query_one(
            db_path, _TX_SELECT + " WHERE t.idempotency_key = ?", (key,)
        )
        return _tx_out(row)  # type: ignore[arg-type]

    _execute(
        db_path,
        """
        INSERT INTO transactions
            (type, amount, currency, account_id, merchant_id, category_id, category,
             description, source, confidence, idempotency_key, tx_date)
        VALUES (?, ?, 'IDR', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ttype, float(amount_dec), account_id, merchant_id, category_id, category,
            description, source, confidence, key, tx.isoformat(),
        ),
    )
    row = _query_one(db_path, _TX_SELECT + " WHERE t.idempotency_key = ?", (key,))
    if row is None:  # pragma: no cover - should never happen
        raise LedgerError("Transaction insert failed")
    return _tx_out(row)


def get_transaction(db_path: str, tx_id: int) -> Optional[Dict[str, Any]]:
    row = _query_one(db_path, _TX_SELECT + " WHERE t.id = ?", (tx_id,))
    return _tx_out(row) if row else None


def list_transactions(
    db_path: str,
    *,
    ttype: Optional[str] = None,
    account_id: Optional[int] = None,
    merchant_id: Optional[int] = None,
    category: Optional[str] = None,
    category_id: Optional[int] = None,
    start_date: Any = None,
    end_date: Any = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    where: List[str] = []
    params: List[Any] = []
    if ttype:
        where.append("t.type = ?")
        params.append(ttype)
    if account_id is not None:
        where.append("t.account_id = ?")
        params.append(account_id)
    if merchant_id is not None:
        where.append("t.merchant_id = ?")
        params.append(merchant_id)
    if category:
        where.append("t.category = ?")
        params.append(category)
    if category_id is not None:
        where.append("t.category_id = ?")
        params.append(category_id)
    if start_date:
        where.append("t.tx_date >= ?")
        params.append(_parse_date(start_date).isoformat())
    if end_date:
        where.append("t.tx_date <= ?")
        params.append(_parse_date(end_date).isoformat())
    if search:
        where.append("(t.description LIKE ? OR t.category LIKE ? OR COALESCE(m.name, '') LIKE ?)")
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern])

    sql = _TX_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY t.tx_date DESC, t.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return [_tx_out(r) for r in _query(db_path, sql, tuple(params))]


def delete_transaction(db_path: str, tx_id: int) -> bool:
    row = get_transaction(db_path, tx_id)
    if row is None:
        raise NotFoundError(f"Transaction not found: {tx_id}")
    if row["type"] == TRANSFER_TYPE:
        raise ConflictError(
            "Transfer legs must be deleted atomically via delete_transfer(pair_key)"
        )
    _execute(db_path, "DELETE FROM transactions WHERE id = ?", (tx_id,))
    return True


# ══════════════════════════════════════════════════════════════════════════════
# § Transfers (double-entry)
# ══════════════════════════════════════════════════════════════════════════════

def record_transfer(
    db_path: str,
    *,
    from_account_id: int,
    to_account_id: int,
    amount: float,
    tx_date: Any,
    description: Optional[str] = None,
    source: str = "manual",
    confidence: Optional[float] = None,
    pair_key: Optional[str] = None,
    check_balance: bool = True,
) -> Dict[str, Any]:
    ensure_schema(db_path)
    if from_account_id == to_account_id:
        raise ValidationError("Transfer source and destination must differ")
    if not get_account(db_path, from_account_id):
        raise NotFoundError(f"Account not found: {from_account_id}")
    if not get_account(db_path, to_account_id):
        raise NotFoundError(f"Account not found: {to_account_id}")
    amount_dec = _to_amount(amount)
    tx = _parse_date(tx_date)
    today = date.today()
    if tx > today:
        raise ValidationError("Date cannot be in the future")

    key = (pair_key or "").strip() or f"tfr:{uuid.uuid4().hex}"
    existing_pair = _query_one(
        db_path, "SELECT * FROM transfer_pairs WHERE pair_key = ?", (key,)
    )
    if existing_pair:
        return _transfer_out(db_path, existing_pair)

    if check_balance:
        balance = account_balance(db_path, from_account_id, as_of=tx)
        if balance < float(amount_dec):
            raise InsufficientFundsError(
                f"Insufficient funds in account {from_account_id}: balance {balance} < {float(amount_dec)}"
            )

    key_from = f"{key}:from"
    key_to = f"{key}:to"
    desc = description or "Transfer"
    ctf = float(amount_dec)
    if _is_postgres_target(db_path):
        # Atomic single-statement DML CTE (PostgreSQL supports data-modifying CTEs).
        sql = """
            WITH legs AS (
                INSERT INTO transactions
                    (type, amount, account_id, description, source, confidence, idempotency_key, tx_date)
                VALUES
                    ('transfer', ?, ?, ?, ?, ?, ?, ?),
                    ('transfer', ?, ?, ?, ?, ?, ?, ?)
                RETURNING id, idempotency_key
            )
            INSERT INTO transfer_pairs (from_transaction_id, to_transaction_id, amount, pair_key)
            SELECT
                (SELECT id FROM legs WHERE idempotency_key = ?),
                (SELECT id FROM legs WHERE idempotency_key = ?),
                ?,
                ?
        """
        params = (
            ctf, from_account_id, desc, source, confidence, key_from, tx.isoformat(),
            ctf, to_account_id, desc, source, confidence, key_to, tx.isoformat(),
            key_from, key_to, ctf, key,
        )
        _execute(db_path, sql, params)
    else:
        # SQLite: explicit transaction on a single connection keeps both legs
        # and the pair atomic (this build has no DML CTE support).
        leg_sql = (
            "INSERT INTO transactions "
            "(type, amount, account_id, description, source, confidence, idempotency_key, tx_date) "
            "VALUES ('transfer', ?, ?, ?, ?, ?, ?, ?)"
        )
        con = sqlite3.connect(db_path)
        try:
            cur = con.cursor()
            cur.execute("BEGIN")
            cur.execute(leg_sql, (ctf, from_account_id, desc, source, confidence, key_from, tx.isoformat()))
            from_id = cur.lastrowid
            cur.execute(leg_sql, (ctf, to_account_id, desc, source, confidence, key_to, tx.isoformat()))
            to_id = cur.lastrowid
            cur.execute(
                "INSERT INTO transfer_pairs (from_transaction_id, to_transaction_id, amount, pair_key) "
                "VALUES (?, ?, ?, ?)",
                (from_id, to_id, ctf, key),
            )
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    pair = _query_one(db_path, "SELECT * FROM transfer_pairs WHERE pair_key = ?", (key,))
    if pair is None:  # pragma: no cover - should never happen
        raise LedgerError("Transfer insert failed")
    return _transfer_out(db_path, pair)


def _transfer_out(db_path: str, pair: Dict[str, Any]) -> Dict[str, Any]:
    from_tx = get_transaction(db_path, pair["from_transaction_id"])
    to_tx = get_transaction(db_path, pair["to_transaction_id"])
    return {
        "pair_id": pair["id"],
        "pair_key": pair["pair_key"],
        "amount": _as_amount(pair["amount"]),
        "from_transaction_id": pair["from_transaction_id"],
        "from_account_id": from_tx["account_id"] if from_tx else None,
        "to_transaction_id": pair["to_transaction_id"],
        "to_account_id": to_tx["account_id"] if to_tx else None,
        "tx_date": str(from_tx.get("tx_date")) if from_tx else None,
        "description": from_tx.get("description") if from_tx else None,
        "source": from_tx.get("source") if from_tx else None,
    }


def get_transfer(db_path: str, pair_key: str) -> Optional[Dict[str, Any]]:
    pair = _query_one(db_path, "SELECT * FROM transfer_pairs WHERE pair_key = ?", (pair_key,))
    return _transfer_out(db_path, pair) if pair else None


def list_transfers(db_path: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    pairs = _query(
        db_path,
        "SELECT * FROM transfer_pairs ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return [_transfer_out(db_path, p) for p in pairs]


def delete_transfer(db_path: str, pair_key: str) -> bool:
    """Atomically remove both transfer legs and their pairing."""
    pair = _query_one(db_path, "SELECT * FROM transfer_pairs WHERE pair_key = ?", (pair_key,))
    if pair is None:
        raise NotFoundError(f"Transfer pair not found: {pair_key}")
    from_id = pair["from_transaction_id"]
    to_id = pair["to_transaction_id"]

    if _is_postgres_target(db_path):
        # PostgreSQL supports data-modifying CTEs: one atomic statement.
        sql = """
            WITH del AS (
                DELETE FROM transfer_pairs WHERE pair_key = ?
                RETURNING from_transaction_id, to_transaction_id
            )
            DELETE FROM transactions
            WHERE id IN (SELECT from_transaction_id FROM del)
               OR id IN (SELECT to_transaction_id FROM del)
        """
        _execute(db_path, sql, (pair_key,))
    else:
        # SQLite: explicit transaction on a single connection.
        con = sqlite3.connect(db_path)
        try:
            cur = con.cursor()
            cur.execute("BEGIN")
            cur.execute("DELETE FROM transfer_pairs WHERE pair_key = ?", (pair_key,))
            cur.execute("DELETE FROM transactions WHERE id IN (?, ?)", (from_id, to_id))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    return True


# ══════════════════════════════════════════════════════════════════════════════
# § Backfill from legacy expenses / incomes (idempotent)
# ══════════════════════════════════════════════════════════════════════════════

def backfill_from_legacy(
    db_path: str,
    expense_db: str,
    income_db: str,
    *,
    source: str = "backfill",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Map existing expenses/incomes rows into unified transactions.

    Idempotency keys (`expense:<id>` / `income:<id>`) make the backfill
    re-runnable: already-mapped rows are skipped, never duplicated.
    """
    ensure_schema(db_path)
    seed_defaults(db_path)
    default_acct = list_accounts(db_path)[0]

    result: Dict[str, Any] = {
        "account_id": default_acct["id"],
        "expenses": {"total": 0, "inserted": 0, "skipped": 0, "errors": 0},
        "incomes": {"total": 0, "inserted": 0, "skipped": 0, "errors": 0},
    }

    expense_rows = _query(
        expense_db,
        "SELECT id, amount, description, category, date FROM expenses ORDER BY id",
    )
    result["expenses"]["total"] = len(expense_rows)
    for row in expense_rows:
        key = f"expense:{row['id']}"
        if _tx_exists(db_path, key):
            result["expenses"]["skipped"] += 1
            continue
        if dry_run:
            result["expenses"]["inserted"] += 1
            continue
        try:
            category_id = _get_or_create_category(
                db_path, (row.get("category") or "Other"), "expense"
            )["id"]
            record_transaction(
                db_path,
                ttype="expense",
                amount=row["amount"],
                tx_date=row["date"],
                account_id=default_acct["id"],
                category_id=category_id,
                category=(row.get("category") or "Other"),
                description=(row.get("description") or row.get("category") or "Expense"),
                source=source,
                idempotency_key=key,
            )
            result["expenses"]["inserted"] += 1
        except LedgerError as exc:
            result["expenses"]["errors"] += 1
            logger.warning("Backfill skipped expense id=%s: %s", row["id"], exc)

    income_rows = _query(
        income_db,
        "SELECT id, amount, source, income_type, description, date FROM incomes ORDER BY id",
    )
    result["incomes"]["total"] = len(income_rows)
    for row in income_rows:
        key = f"income:{row['id']}"
        if _tx_exists(db_path, key):
            result["incomes"]["skipped"] += 1
            continue
        if dry_run:
            result["incomes"]["inserted"] += 1
            continue
        try:
            category_id = _get_or_create_category(
                db_path, (row.get("income_type") or "Salary"), "income"
            )["id"]
            record_transaction(
                db_path,
                ttype="income",
                amount=row["amount"],
                tx_date=row["date"],
                account_id=default_acct["id"],
                category_id=category_id,
                category=(row.get("income_type") or "Salary"),
                description=(row.get("description") or row.get("source") or "Income"),
                source=source,
                idempotency_key=key,
            )
            result["incomes"]["inserted"] += 1
        except LedgerError as exc:
            result["incomes"]["errors"] += 1
            logger.warning("Backfill skipped income id=%s: %s", row["id"], exc)

    return result
