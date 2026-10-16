"""
backend/routers/ledger.py — Unified transaction & account API (Phase 2)
========================================================================
High Cohesion: owns only /api/transactions, /api/accounts, /api/categories,
/api/merchants routes backed by packages/api/backend/finance/ledger_engine.py.

Low Coupling: depends only on deps.py / ledger_engine.py / security.core.
"""

import logging
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from packages.api.backend.finance.ledger_engine import (
    ACCOUNT_TYPES,
    CATEGORY_KINDS,
    SUPPORTED_TYPES,
    ConflictError,
    DuplicateError,
    InsufficientFundsError,
    LedgerError,
    NotFoundError,
    ValidationError,
    account_balance,
    backfill_from_legacy,
    create_account,
    create_category,
    delete_account,
    delete_category,
    delete_transaction,
    delete_transfer,
    ensure_schema,
    forget_merchant,
    get_account,
    get_transaction,
    get_transfer,
    list_accounts,
    list_categories,
    list_merchants,
    list_transactions,
    list_transfers,
    record_transaction,
    record_transfer,
    remember_merchant,
    seed_defaults,
    update_account,
    update_category,
)
from packages.api.backend.security.core import require_scope
from packages.core.infrastructure.config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


def _ledger_db() -> str:
    return Config.get_db_path("finance")


def _map_ledger_error(exc: LedgerError) -> HTTPException:
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (DuplicateError, ConflictError)):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, InsufficientFundsError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def _ensure() -> None:
    path = _ledger_db()
    if path in _ensured_paths:
        return
    with _ensure_lock:
        if path in _ensured_paths:
            return
        ensure_schema(path)
        seed_defaults(path)
        _ensured_paths.add(path)


_ensured_paths: set = set()
_ensure_lock = threading.Lock()


# ═════════════════════════════════════════════════════════════════════════════
# Schemas
# ═════════════════════════════════════════════════════════════════════════════

class AccountIn(BaseModel):
    name: str
    type: str = "bank"
    currency: str = "IDR"
    opening_balance: float = 0.0
    is_default: bool = False

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("Account name cannot be empty")
        return v

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: str) -> str:
        if v not in ACCOUNT_TYPES:
            raise ValueError(f"Invalid account type; allowed: {sorted(ACCOUNT_TYPES)}")
        return v


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    currency: Optional[str] = None
    opening_balance: Optional[float] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class CategoryIn(BaseModel):
    name: str
    kind: str = "expense"
    color: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("Category name cannot be empty")
        return v

    @field_validator("kind")
    @classmethod
    def kind_valid(cls, v: str) -> str:
        if v not in CATEGORY_KINDS:
            raise ValueError(f"Invalid category kind; allowed: {sorted(CATEGORY_KINDS)}")
        return v


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


class TransactionIn(BaseModel):
    type: str
    amount: float
    tx_date: str
    account_id: Optional[int] = None
    merchant_id: Optional[int] = None
    category_id: Optional[int] = None
    category: Optional[str] = None
    description: Optional[str] = None
    source: str = "manual"
    confidence: Optional[float] = None
    idempotency_key: Optional[str] = None

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: str) -> str:
        if v not in SUPPORTED_TYPES:
            raise ValueError(f"Unsupported transaction type; allowed: {sorted(SUPPORTED_TYPES)}")
        return v


class TransferIn(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: float
    tx_date: str
    description: Optional[str] = None
    source: str = "manual"
    confidence: Optional[float] = None
    pair_key: Optional[str] = None
    check_balance: bool = True


class MerchantIn(BaseModel):
    name: str
    category: Optional[str] = None
    category_id: Optional[int] = None
    display_name: Optional[str] = None


# ═════════════════════════════════════════════════════════════════════════════
# Transactions
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/api/transactions", dependencies=[Depends(require_scope("read"))])
def list_tx(
    type: Optional[str] = None,
    account_id: Optional[int] = None,
    merchant_id: Optional[int] = None,
    category: Optional[str] = None,
    category_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    _ensure()
    try:
        items = list_transactions(
            _ledger_db(),
            ttype=type,
            account_id=account_id,
            merchant_id=merchant_id,
            category=category,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
            search=search,
            limit=min(limit, 500),
            offset=offset,
        )
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"items": items, "limit": limit, "offset": offset, "total": len(items)}


@router.post("/api/transactions", dependencies=[Depends(require_scope("write"))])
def add_tx(body: TransactionIn):
    _ensure()
    try:
        row = record_transaction(
            _ledger_db(),
            ttype=body.type,
            amount=body.amount,
            tx_date=body.tx_date,
            account_id=body.account_id,
            merchant_id=body.merchant_id,
            category_id=body.category_id,
            category=body.category,
            description=body.description,
            source=body.source,
            confidence=body.confidence,
            idempotency_key=body.idempotency_key,
        )
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"ok": True, "id": row["id"], "transaction": row}


@router.post("/api/transactions/transfer", dependencies=[Depends(require_scope("write"))])
def add_transfer(body: TransferIn):
    _ensure()
    try:
        result = record_transfer(
            _ledger_db(),
            from_account_id=body.from_account_id,
            to_account_id=body.to_account_id,
            amount=body.amount,
            tx_date=body.tx_date,
            description=body.description,
            source=body.source,
            confidence=body.confidence,
            pair_key=body.pair_key,
            check_balance=body.check_balance,
        )
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"ok": True, **result}


@router.get("/api/transactions/transfers", dependencies=[Depends(require_scope("read"))])
def list_tf(limit: int = 100, offset: int = 0):
    _ensure()
    return {"items": list_transfers(_ledger_db(), limit=min(limit, 500), offset=offset)}


@router.get("/api/transactions/transfer/{pair_key}", dependencies=[Depends(require_scope("read"))])
def get_tf(pair_key: str):
    _ensure()
    result = get_transfer(_ledger_db(), pair_key)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Transfer pair not found: {pair_key}")
    return result


@router.delete("/api/transactions/transfer/{pair_key}", dependencies=[Depends(require_scope("write"))])
def delete_tf(pair_key: str):
    _ensure()
    try:
        delete_transfer(_ledger_db(), pair_key)
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"ok": True}


@router.post("/api/transactions/backfill", dependencies=[Depends(require_scope("write"))])
def backfill(dry_run: bool = False):
    _ensure()
    expense_db = Config.get_db_path("expense")
    income_db = Config.get_db_path("income")
    try:
        result = backfill_from_legacy(
            _ledger_db(), expense_db, income_db, dry_run=dry_run
        )
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"ok": True, **result}


@router.get("/api/transactions/{tx_id}", dependencies=[Depends(require_scope("read"))])
def get_tx(tx_id: int):
    _ensure()
    row = get_transaction(_ledger_db(), tx_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Transaction not found: {tx_id}")
    return row


@router.delete("/api/transactions/{tx_id}", dependencies=[Depends(require_scope("write"))])
def delete_tx(tx_id: int):
    _ensure()
    try:
        delete_transaction(_ledger_db(), tx_id)
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"ok": True}


# ═════════════════════════════════════════════════════════════════════════════
# Accounts
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/api/accounts", dependencies=[Depends(require_scope("read"))])
def list_acc(include_inactive: bool = False):
    _ensure()
    return {"items": list_accounts(_ledger_db(), include_inactive=include_inactive)}


@router.post("/api/accounts", dependencies=[Depends(require_scope("write"))])
def add_acc(body: AccountIn):
    _ensure()
    try:
        row = create_account(
            _ledger_db(),
            name=body.name,
            account_type=body.type,
            currency=body.currency,
            opening_balance=body.opening_balance,
            is_default=body.is_default,
        )
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"ok": True, "id": row["id"], "account": row}


@router.get("/api/accounts/{account_id}", dependencies=[Depends(require_scope("read"))])
def get_acc(account_id: int):
    _ensure()
    row = get_account(_ledger_db(), account_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Account not found: {account_id}")
    return row


@router.get("/api/accounts/{account_id}/balance", dependencies=[Depends(require_scope("read"))])
def get_acc_balance(account_id: int, as_of: Optional[str] = None):
    _ensure()
    try:
        balance = account_balance(_ledger_db(), account_id, as_of=as_of)
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"account_id": account_id, "balance": balance}


@router.put("/api/accounts/{account_id}", dependencies=[Depends(require_scope("write"))])
def update_acc(account_id: int, body: AccountUpdate):
    _ensure()
    try:
        row = update_account(
            _ledger_db(),
            account_id,
            **body.model_dump(exclude_none=True),
        )
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"ok": True, "account": row}


@router.delete("/api/accounts/{account_id}", dependencies=[Depends(require_scope("write"))])
def delete_acc(account_id: int):
    _ensure()
    try:
        delete_account(_ledger_db(), account_id)
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"ok": True}


# ═════════════════════════════════════════════════════════════════════════════
# Categories
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/api/categories", dependencies=[Depends(require_scope("read"))])
def list_cat(kind: Optional[str] = None):
    _ensure()
    return {"items": list_categories(_ledger_db(), kind=kind)}


@router.post("/api/categories", dependencies=[Depends(require_scope("write"))])
def add_cat(body: CategoryIn):
    _ensure()
    try:
        row = create_category(
            _ledger_db(), name=body.name, kind=body.kind, color=body.color
        )
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"ok": True, "id": row["id"], "category": row}


@router.put("/api/categories/{category_id}", dependencies=[Depends(require_scope("write"))])
def update_cat(category_id: int, body: CategoryUpdate):
    _ensure()
    try:
        row = update_category(
            _ledger_db(), category_id, name=body.name, color=body.color
        )
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"ok": True, "category": row}


@router.delete("/api/categories/{category_id}", dependencies=[Depends(require_scope("write"))])
def delete_cat(category_id: int):
    _ensure()
    try:
        delete_category(_ledger_db(), category_id)
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"ok": True}


# ═════════════════════════════════════════════════════════════════════════════
# Merchants
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/api/merchants", dependencies=[Depends(require_scope("read"))])
def list_mer(limit: int = 200):
    _ensure()
    return {"items": list_merchants(_ledger_db(), limit=min(limit, 1000))}


@router.post("/api/merchants", dependencies=[Depends(require_scope("write"))])
def add_mer(body: MerchantIn):
    _ensure()
    try:
        row = remember_merchant(
            _ledger_db(),
            name=body.name,
            category=body.category,
            category_id=body.category_id,
            display_name=body.display_name,
        )
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"ok": True, "id": row["id"], "merchant": row}


@router.delete("/api/merchants/{merchant_id}", dependencies=[Depends(require_scope("write"))])
def delete_mer(merchant_id: int):
    _ensure()
    try:
        forget_merchant(_ledger_db(), merchant_id)
    except LedgerError as exc:
        raise _map_ledger_error(exc)
    return {"ok": True}
