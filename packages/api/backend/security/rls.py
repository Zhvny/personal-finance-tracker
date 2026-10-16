"""Per-request Postgres RLS context.

Holds the current user id in a ContextVar so every database call made
within a request can stamp ``app.current_user_id`` on its Postgres
session via ``set_config(..., is_local=true)``. Read by
``DatabaseManager.get_connection`` / ``DatabaseManager.transaction``.

The GUC is consulted by the RLS policies in
``migrations/006_auth_and_rls_policies.sql``. Without setting it, the
policies deny all rows for non-admin connections (the audit flagged
this as effectively dead RLS — see A-C03).

Security:
- Only ``verify_api_key`` / the auth dependency writes the var.
- The value is opaque from the user's perspective; the GUC's purpose
  is row visibility, not authorization decisions.
- ``clear()`` MUST be called at the end of every request to avoid
  leaking context across pooled connections (ContextVar handles
  this implicitly per asyncio task, but the explicit clear is a
  belt-and-suspenders against future threadpool usage).
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

# Sentinel for "no current user set" (e.g., unauthenticated probes).
# Using a non-empty string avoids the special-cased "GUC missing" path
# in current_setting('app.current_user_id', true) which returns NULL
# (and breaks = comparisons).
_UNSET = ""

_current_user_id_var: ContextVar[str] = ContextVar("alpha_current_user_id", default=_UNSET)


def set_current_user_id(user_id: str) -> None:
    """Stamp the current request's user id. Called by verify_api_key."""
    _current_user_id_var.set(user_id)


def get_current_user_id() -> Optional[str]:
    """Return the active user id, or None if unset."""
    val = _current_user_id_var.get()
    return val if val and val != _UNSET else None


def clear_current_user_id() -> None:
    _current_user_id_var.set(_UNSET)
