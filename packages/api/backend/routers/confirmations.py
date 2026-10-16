"""
backend/routers/confirmations.py — Telegram confirmation API (Phase 3)
========================================================================
High Cohesion: owns only /api/chat-bindings and /api/confirmations routes
backed by packages/api/backend/finance/confirmation_engine.py.

Low Coupling: depends only on Config / confirmation_engine.py / security.core.
The ledger commit target is the canonical `finance` db path (active profile).
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from packages.api.backend.finance.confirmation_engine import (
    ConfirmationError,
    ConflictError,
    NotFoundError,
    ValidationError,
    bind_chat,
    cancel_all_pending,
    cancel_draft,
    confirm_draft,
    create_draft,
    expire_stale,
    get_binding,
    get_draft,
    list_all_drafts,
    list_bindings,
    list_drafts,
    require_binding,
    update_draft,
)
from packages.api.backend.security.core import require_scope
from packages.core.infrastructure.config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


def _chat_db() -> str:
    return Config.get_db_path("chat")


def _ledger_db() -> str:
    return Config.get_db_path("finance")


def _map_error(exc: ConfirmationError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


# ── Chat bindings (per-chat auth) ──────────────────────────────────────────────

class BindChatBody(BaseModel):
    chat_id: int
    profile: Optional[str] = None
    display_name: Optional[str] = None


@router.post("/api/chat-bindings", dependencies=[Depends(require_scope("write"))])
def api_bind_chat(body: BindChatBody):
    try:
        return bind_chat(_chat_db(), body.chat_id, profile=body.profile, display_name=body.display_name)
    except ConfirmationError as exc:
        raise _map_error(exc) from exc


@router.get("/api/chat-bindings", dependencies=[Depends(require_scope("read"))])
def api_list_bindings():
    return {"bindings": list_bindings(_chat_db())}


@router.get("/api/chat-bindings/{chat_id}", dependencies=[Depends(require_scope("read"))])
def api_get_binding(chat_id: int):
    binding = get_binding(_chat_db(), chat_id)
    if not binding:
        raise HTTPException(status_code=404, detail=f"Chat {chat_id} is not bound")
    return binding


# ── Confirmation drafts ────────────────────────────────────────────────────────

class CreateDraftBody(BaseModel):
    chat_id: int
    draft: Dict[str, Any]
    profile: Optional[str] = None
    message_id: Optional[int] = None


@router.post("/api/confirmations/drafts", dependencies=[Depends(require_scope("write"))])
def api_create_draft(body: CreateDraftBody):
    try:
        return create_draft(
            _chat_db(),
            body.chat_id,
            body.draft,
            profile=body.profile,
            message_id=body.message_id,
        )
    except ConfirmationError as exc:
        raise _map_error(exc) from exc


@router.get("/api/confirmations", dependencies=[Depends(require_scope("read"))])
def api_list_confirmations(
    chat_id: int,
    status: str = "pending",
    limit: int = 100,
):
    try:
        require_binding(_chat_db(), chat_id)
        if status == "all":
            return {"confirmations": list_all_drafts(_chat_db(), chat_id, limit=limit)}
        return {"confirmations": list_drafts(_chat_db(), chat_id, status=status, limit=limit)}
    except ConfirmationError as exc:
        raise _map_error(exc) from exc


@router.get("/api/confirmations/{token}", dependencies=[Depends(require_scope("read"))])
def api_get_confirmation(token: str):
    try:
        return get_draft(_chat_db(), token)
    except ConfirmationError as exc:
        raise _map_error(exc) from exc


class UpdateDraftBody(BaseModel):
    draft: Optional[Dict[str, Any]] = None
    edit_target: Optional[str] = None
    message_id: Optional[int] = None


@router.patch("/api/confirmations/{token}", dependencies=[Depends(require_scope("write"))])
def api_update_confirmation(token: str, body: UpdateDraftBody):
    try:
        return update_draft(
            _chat_db(),
            token,
            draft=body.draft,
            edit_target=body.edit_target,
            message_id=body.message_id,
        )
    except ConfirmationError as exc:
        raise _map_error(exc) from exc


@router.post("/api/confirmations/{token}/confirm", dependencies=[Depends(require_scope("write"))])
def api_confirm(token: str):
    try:
        return confirm_draft(_chat_db(), token, ledger_db_path=_ledger_db())
    except ConfirmationError as exc:
        raise _map_error(exc) from exc


@router.post("/api/confirmations/{token}/cancel", dependencies=[Depends(require_scope("write"))])
def api_cancel(token: str):
    try:
        return cancel_draft(_chat_db(), token)
    except ConfirmationError as exc:
        raise _map_error(exc) from exc


@router.post("/api/confirmations/chat/{chat_id}/cancel-all", dependencies=[Depends(require_scope("write"))])
def api_cancel_all(chat_id: int):
    try:
        count = cancel_all_pending(_chat_db(), chat_id)
        return {"cancelled": count}
    except ConfirmationError as exc:
        raise _map_error(exc) from exc


@router.post("/api/confirmations/expire-stale", dependencies=[Depends(require_scope("write"))])
def api_expire_stale():
    try:
        count = expire_stale(_chat_db())
        return {"expired": count}
    except ConfirmationError as exc:
        raise _map_error(exc) from exc
