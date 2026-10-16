"""Shared service-to-service token (audit A-H06).

The Alpha gateway (:8444) reverse-proxies every request to one of the
downstream services (:8450-:8455). Without a shared token, any container
on the same Docker network could call the downstream services directly,
bypassing gateway-level rate limiting, IP whitelisting, and audit.

The token is a long random secret shared between the gateway and all
downstream services via the ``ALPHA_SERVICE_TOKEN`` env var. The gateway
attaches it as ``X-Service-Token`` on every proxied request; downstreams
verify it before honoring the request.

Generation:
  - If ``ALPHA_SERVICE_TOKEN`` is unset, the first process that imports
    this module generates one and stores it in the env so sibling
    processes started in the same shell inherit the same value.
  - In production, refuse to start without an explicit value (avoids
    each pod minting its own and breaking the trust contract).
  - Dev mode (``FINANCE_TRACKER_DEV_MODE=1``) + loopback caller =>
    bypass the check (mirrors the existing DEV_MODE loopback carve-out
    in security.core.verify_api_key).

This is intentionally NOT the same as the user-facing
``FINANCE_TRACKER_API_KEY``. Mixing the two would let a leaked user key
grant service-tier access.
"""
from __future__ import annotations

import logging
import os
import secrets
from threading import Lock

logger = logging.getLogger("alpha.service_token")

_LOCK = Lock()
_HEADER = "X-Service-Token"


def _is_production() -> bool:
    env = (os.environ.get("ENVIRONMENT") or os.environ.get("APP_ENV") or "").lower()
    return env in ("production", "prod")


def _is_dev_mode() -> bool:
    # Audit T3 (2026-09-02): mirror the production-guard from
    # ``packages.api.backend.security.core:dev_mode_active``. The previous
    # implementation returned True unconditionally when the env var was
    # set, which meant a misconfigured prod deploy that left
    # ``FINANCE_TRACKER_DEV_MODE=1`` in .env would silently bypass the
    # service-token check (auth-by-bypass). Production env now always
    # returns False regardless of the flag.
    if _is_production():
        return False
    return os.environ.get("FINANCE_TRACKER_DEV_MODE", "0") == "1"


def get_service_token() -> str:
    """Return the active service token, generating one on first call if needed.

    The first caller stores the generated value in ``os.environ`` so that
    sibling processes started from the same shell (or the same docker
    compose ``up``) pick it up. This avoids the dev-time footgun of each
    container minting its own ephemeral token.
    """
    with _LOCK:
        existing = os.environ.get("ALPHA_SERVICE_TOKEN", "").strip()
        if existing:
            return existing
        if _is_production():
            raise RuntimeError(
                "ALPHA_SERVICE_TOKEN must be set in production. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        token = secrets.token_urlsafe(32)
        os.environ["ALPHA_SERVICE_TOKEN"] = token
        logger.warning(
            "[service_token] ALPHA_SERVICE_TOKEN not set — generated ephemeral value for this process. "
            "Set it explicitly in .env to ensure all containers agree."
        )
        return token


def should_require_service_token(client_ip: str = "") -> bool:
    """Return True if the active request must carry a valid service token.

    Bypassed for dev mode + loopback (mirrors the existing dev carve-out
    in verify_api_key). Production always requires it.
    """
    if _is_dev_mode():
        from packages.api.backend.security.core import LOOPBACK_IPS
        if client_ip in LOOPBACK_IPS or client_ip == "":
            return False
    return True


def verify_service_token(provided: str | None, client_ip: str = "") -> bool:
    """Constant-time check that ``provided`` matches the shared token."""
    if not should_require_service_token(client_ip):
        return True
    expected = get_service_token()
    if not provided:
        return False
    import hmac
    return hmac.compare_digest(provided, expected)


def inject_service_token(headers: dict[str, str]) -> dict[str, str]:
    """Add ``X-Service-Token`` to an outbound header dict (gateway side)."""
    headers[_HEADER] = get_service_token()
    return headers
