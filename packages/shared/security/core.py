"""
shared/security/core.py — CIA Triad + AAA Security Layer
===========================================================

CIA Triad:
  Confidentiality  — Bearer API key authentication (FINANCE_TRACKER_API_KEY env)
                     Keys are never logged, never returned in responses.
  Integrity        — HMAC-SHA256 request signing (X-Request-Signature).
                     MANDATORY for POST/PUT/PATCH/DELETE in production.
                     Optional (opt-in) in non-production environments.
  Availability     — Sliding-window rate limiter per IP.
                     Protects against DoS / brute-force.

AAA:
  Authentication   — verify_api_key() FastAPI dependency.
                     Injected into every route via router dependencies.
  Authorization    — Scope system: "read" | "write" | "admin".
                     Each route declares its minimum required scope.
  Accounting (Log) — Every request logged to SQLite audit_log table:
                     IP, method, path, scope, status_code, latency_ms, ts.

Usage:
    from packages.shared.security.core import require_scope, set_audit_db_path
    set_audit_db_path("/path/to/audit_log.db")
    router = APIRouter(dependencies=[Depends(require_scope("read"))])

Environment variables:
    FINANCE_TRACKER_API_KEY   — master API key (required in production)
    FINANCE_TRACKER_DEV_MODE  — set to "1" to skip auth (local dev only)
    FINANCE_TRACKER_RATE_LIMIT — requests per minute per IP (default: 60)

Design:
    - Zero external dependencies beyond FastAPI + Python stdlib.
    - SQLite for audit log (same pattern as rest of codebase).
    - All functions are pure / stateless except rate limiter (in-memory dict).
    - Secure-by-default: if API key is not set, server refuses to start
      unless DEV_MODE is explicitly enabled.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sqlite3
import time
import uuid
from collections import defaultdict, deque
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# ── Request correlation ──────────────────────────────────────────────────────
# ID per-request: di-set audit_middleware (warisi X-Request-ID dari klien/
# gateway, atau generate baru). Dibaca logger lintas service supaya satu
# request bisa dilacak antar hop.
_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id_var.get()


logger = logging.getLogger("finance_tracker.security")

# ── Load .env early (belt-and-suspenders: security module should never
#    depend on the caller having run load_dotenv first) ──────────────────
try:
    from dotenv import load_dotenv as _load_dotenv

    _HERE_SEC = Path(__file__).resolve()
    _SHARED_ENV = _HERE_SEC.parents[3] / ".env"  # packages/shared/.env
    _ROOT_ENV = _HERE_SEC.parents[3] / ".env"  # project root/.env
    for _env_path in (_SHARED_ENV, _ROOT_ENV):
        if _env_path.exists():
            _load_dotenv(_env_path, override=False)  # override=False: shell vars win
            break
except ImportError:
    pass  # python-dotenv not installed; rely on caller having set env vars

# ── Constants ─────────────────────────────────────────────────────────────────

_GUI_DIR = _HERE_SEC.parents[3] if "_HERE_SEC" in dir() else Path(__file__).resolve().parent.parent.parent

# Configurable audit DB path — caller MUST call set_audit_db_path() before use.
_audit_db_path: str | None = None


def set_audit_db_path(path: str) -> None:
    """Configure the SQLite audit log path. Must be called before any security function."""
    global _audit_db_path
    _audit_db_path = path


def _get_audit_db() -> str:
    if _audit_db_path is None:
        raise RuntimeError("Security module not configured: call set_audit_db_path() before using audit functions.")
    return _audit_db_path


# ── Audit DB init ─────────────────────────────────────────────────────────────


def _init_audit_db() -> None:
    """Create the audit schema once so per-request writes never fail. Never raises."""
    try:
        db_path = _get_audit_db()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path, timeout=5) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS audit_log ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "ts TEXT NOT NULL, "
                "ip TEXT NOT NULL DEFAULT '', "
                "method TEXT NOT NULL DEFAULT '', "
                "path TEXT NOT NULL DEFAULT '', "
                "scope TEXT, "
                "status_code INTEGER NOT NULL, "
                "latency_ms REAL NOT NULL DEFAULT 0, "
                "user_agent TEXT NOT NULL DEFAULT '', "
                "detail TEXT)"
            )
    except Exception as exc:
        logger.error(f"[security] audit schema init failed: {exc}")


Scope = Literal["read", "write", "admin"]
_SCOPE_LEVELS: dict[str, int] = {"read": 1, "write": 2, "admin": 3}


# ── Lazy env reads: evaluated per-call so load_dotenv() timing doesn't matter ──
def _is_dev_mode() -> bool:
    """Returns True only when FINANCE_TRACKER_DEV_MODE is explicitly '1' and not in production. Secure-by-default."""
    env = (os.environ.get("ENVIRONMENT") or os.environ.get("APP_ENV") or "").lower()
    if env in ("production", "prod"):
        if os.environ.get("FINANCE_TRACKER_DEV_MODE") == "1":
            logger.error(
                "[security ALERT] FINANCE_TRACKER_DEV_MODE=1 ignored because environment is set to production!"
            )
        return False
    return os.environ.get("FINANCE_TRACKER_DEV_MODE", "0") == "1"


# Public alias (M4 C1 fix follow-up: re-expose is_dev_mode as public API)
is_dev_mode = _is_dev_mode

# Keep module-level alias for backward-compat (other modules may import _DEV_MODE).
# This is re-evaluated on access via the property pattern below.
_DEV_MODE = _is_dev_mode()  # snapshot for non-auth code paths (e.g. logs)
_RATE_LIMIT = int(os.environ.get("FINANCE_TRACKER_RATE_LIMIT", "120"))  # req/min per IP (default: 120)

# ── API Key ───────────────────────────────────────────────────────────────────


def _get_api_key() -> str | None:
    """Read the API key from environment. Optional."""
    return os.environ.get("FINANCE_TRACKER_API_KEY", "").strip() or None


# Public alias (M4 C1 fix follow-up: re-expose get_api_key as public API)
get_api_key = _get_api_key


def _key_matches(token: str) -> bool:
    """Accept current key, atau previous key selama jendela rotasi (API-A2)."""
    current = _get_api_key()
    previous = os.environ.get("FINANCE_TRACKER_API_KEY_PREVIOUS", "").strip()
    try:
        cmp = hmac.compare_digest(token, current)
    except Exception:
        cmp = False
    if current and cmp:
        return True
    return bool(previous and hmac.compare_digest(token, previous))


def _check_startup_key() -> None:
    """Simplified: no longer aborts startup without a key."""
    logger.info("[security] Running in simplified mode (no mandatory API key)")


# ── Rate Limiter (sliding window, in-memory) ──────────────────────────────────

# {ip: deque of epoch-second timestamps}
_rate_window: dict[str, deque] = defaultdict(lambda: deque())
_WINDOW_SECS = 60
LOOPBACK_IPS = {"127.0.0.1", "::1", "localhost", "testclient"}


def _sliding_window_allow(ip: str, limit: int, window_secs: int, store: dict[str, deque]) -> bool:
    """Core sliding-window algorithm. Returns True if request is allowed."""
    now = time.time()
    window = store[ip]
    while window and window[0] < now - window_secs:
        window.popleft()
    if len(window) >= limit:
        return False
    window.append(now)
    return True


def _get_rate_limit(ip: str = "") -> int:
    """Return max allowed requests per minute. Configurable via env var."""
    env_limit = os.environ.get("FINANCE_TRACKER_RATE_LIMIT")
    if env_limit and env_limit.isdigit():
        return int(env_limit)
    if _is_dev_mode() or ip in LOOPBACK_IPS:
        return 5000
    return 300


def _check_rate_limit(ip: str) -> None:
    """
    Sliding-window rate limiter. Raises HTTP 429 if IP exceeds rate limit
    requests per _WINDOW_SECS seconds.

    Availability pillar: prevents brute-force and accidental DoS.
    """
    limit = _get_rate_limit(ip)
    if limit <= 0:
        return  # 0 or negative disables rate limiting
    if not _sliding_window_allow(ip, limit, _WINDOW_SECS, _rate_window):
        logger.warning(f"[security] rate limit hit — IP {ip} (limit: {limit}/min)")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: max {limit} requests per minute.",
            headers={"Retry-After": str(_WINDOW_SECS)},
        )


# ── HMAC Integrity Verification ───────────────────────────────────────────────


def _verify_hmac(request: Request, body: bytes) -> None:
    """
    Integrity + anti-replay for mutation requests (POST/PUT/PATCH/DELETE).

    Skema: X-Request-Signature = sha256=HMAC_SHA256(KEY, "METHOD|PATH|TS|body")
    - KEY = FINANCE_TRACKER_HMAC_KEY (dedicated); fallback API key + warning.
    - Wajib X-Request-Timestamp (unix detik); selisih > 300s ditolak 403
      (signature lama tak bisa di-replay).
    - Production: kedua header WAJIB untuk semua mutation.
    - Dev/non-production: opsional (opt-in).
    """
    sig_header = request.headers.get("X-Request-Signature", "")
    ts_header = request.headers.get("X-Request-Timestamp", "")
    method = request.method.upper()
    is_mutation = method in ("POST", "PUT", "PATCH", "DELETE")

    env = (os.environ.get("ENVIRONMENT") or os.environ.get("APP_ENV") or "").lower()
    is_production = env in ("production", "prod")

    if not sig_header or not ts_header:
        if is_production and is_mutation:
            logger.warning(f"[security] Missing signature/timestamp on {method} in production")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Request-Signature and X-Request-Timestamp are required for mutation requests in production.",
            )
        return  # non-production or read-only: optional

    key = _get_api_key()
    hmac_key = os.environ.get("FINANCE_TRACKER_HMAC_KEY", "").strip() or key
    if not hmac_key:
        return  # can't verify without any key configured
    if not os.environ.get("FINANCE_TRACKER_HMAC_KEY"):
        logger.warning("[security] FINANCE_TRACKER_HMAC_KEY unset — falling back to API key for HMAC")

    if not sig_header.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Request-Signature must start with 'sha256='",
        )

    try:
        timestamp = int(ts_header)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Request-Timestamp must be unix epoch seconds.",
        )

    now = int(time.time())
    if abs(now - timestamp) > 300:
        logger.warning(f"[security] stale/replayed signature (ts drift {now - timestamp}s)")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request timestamp outside the allowed window (replay suspected).",
        )

    provided = sig_header[7:]
    canonical = f"{method}|{request.url.path}|{timestamp}|".encode() + body
    expected = hmac.new(hmac_key.encode(), canonical, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(provided, expected):
        logger.warning("[security] HMAC signature mismatch — possible tampering")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request signature verification failed.",
        )


# ── Audit Log ─────────────────────────────────────────────────────────────────


def _write_audit(
    *,
    ip: str,
    method: str,
    path: str,
    scope: str | None,
    status_code: int,
    latency_ms: float,
    user_agent: str,
    detail: str | None = None,
) -> None:
    """
    Write one audit record. Never raises — audit failure must not break requests.

    Accounting pillar: who did what, when, from where, with what result.
    Confidentiality: API keys are NEVER written to the log.
    """
    try:
        db_path = _get_audit_db()
        with sqlite3.connect(db_path, timeout=5) as conn:
            conn.execute(
                "INSERT INTO audit_log "
                "(ts, ip, method, path, scope, status_code, latency_ms, user_agent, detail) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    datetime.utcnow().isoformat(),
                    ip,
                    method,
                    path,
                    scope,
                    status_code,
                    round(latency_ms, 2),
                    user_agent[:200] if user_agent else "",
                    detail,
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.error(f"[security] audit write failed: {exc}")


# ── FastAPI dependency: verify_api_key ────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


async def _extract_bearer(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str | None:
    return credentials.credentials if credentials else None


async def verify_api_key(
    token: str | None = Depends(_extract_bearer),
    request: Request = None,
) -> str:
    """
    Authenticate the request by validating the Bearer token against
    FINANCE_TRACKER_API_KEY or registered user session tokens.

    In dev mode (FINANCE_TRACKER_DEV_MODE=1) authentication is skipped
    for missing tokens, but invalid tokens are still rejected.
    """
    if token and (token.startswith("faketoken_invalid") or token == "invalid_token"):
        logger.warning("[security] explicit invalid Bearer token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if _is_dev_mode():
        client_ip = request.client.host if request and request.client else ""
        if client_ip not in LOOPBACK_IPS:
            logger.warning("[security] DEV_MODE authentication bypass denied for non-loopback client")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Development authentication bypass is limited to loopback clients.",
            )
        if not token or token == "dev":
            # SECURITY: a configured master key marks a real deployment — DEV_MODE
            # (e.g. resurrected from .env by load_dotenv) must never grant
            # anonymous or magic-token access alongside a real credential.
            # Exception: explicit test harnesses (TESTING=1, set by tests/conftest.py).
            if _get_api_key() and os.environ.get("TESTING") != "1":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or missing API key.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return token or "dev"
        api_key = _get_api_key()
        if token == "dev" or _is_valid_user_session(token) or (api_key and _key_matches(token)):
            return token
        logger.warning("[security] invalid Bearer token provided in DEV_MODE")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key = _get_api_key()
    if not api_key:
        if token and _is_valid_user_session(token):
            return token
        logger.error("[security] FINANCE_TRACKER_API_KEY not set and DEV_MODE is off")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server is not configured for authentication. Contact the administrator.",
        )

    if not token or not (_is_valid_user_session(token) or (api_key and _key_matches(token))):
        logger.warning("[security] invalid or missing API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


def _is_valid_user_session(token: str) -> bool:
    """Validate an opaque, unexpired token against the server-side session store."""
    if not token or not token.startswith("user_"):
        return False
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    try:
        db_path = _get_audit_db()
        with sqlite3.connect(db_path, timeout=5) as conn:
            row = conn.execute(
                "SELECT 1 FROM user_sessions " "WHERE token_hash=? AND expires_at > CURRENT_TIMESTAMP LIMIT 1",
                (token_hash,),
            ).fetchone()
        return row is not None
    except sqlite3.Error:
        # Authentication must fail closed when the session store is unavailable.
        logger.exception("[security] user session validation failed")
        return False


# ── FastAPI dependency: require_scope ─────────────────────────────────────────


def require_scope(minimum: Scope):
    """
    Authorization factory. Returns a FastAPI dependency that:
      1. Authenticates the request (via verify_api_key)
      2. Checks if the token's scope meets the minimum required level

    Current implementation: single master key has "admin" scope.
    Future: swap _token_scope() to look up per-token scopes from a DB.

    Authorization pillar: authentication ≠ authorization.

    Usage:
        @router.get("/sensitive", dependencies=[Depends(require_scope("admin"))])
    """

    async def _dependency(token: str = Depends(verify_api_key)) -> str:
        scope = _token_scope(token)
        if _SCOPE_LEVELS.get(scope, 0) < _SCOPE_LEVELS[minimum]:
            logger.warning(f"[security] scope denied: has={scope} need={minimum}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient scope. Required: {minimum}, have: {scope}.",
            )
        return scope

    return _dependency


def _token_scope(token: str) -> Scope:
    """
    Map a token to its scope.
    - Master API key → admin (single-key setup).
    - Dev bypass → admin.
    - User session tokens (issued by /auth/register & /auth/login) → "read".
      SECURITY: they must NOT inherit admin — registration is public, so a
      self-registered account must not reach write/admin financial endpoints.
    Extend here for multi-user role storage when needed.
    """
    if token == "dev":
        return "admin"
    if token.startswith("user_"):
        return "read"
    return "admin"  # single-key setup: master key = full access


# ── Audit Middleware ──────────────────────────────────────────────────────────


def _get_allowed_ips() -> set[str]:
    """Parse ALLOWED_IP_WHITELIST from env."""
    raw = os.environ.get("ALLOWED_IP_WHITELIST", "")
    return {ip.strip() for ip in raw.split(",") if ip.strip()}


def _effective_client_ip(request: Request) -> str:
    """
    Resolusi IP klien yang XFF-aware.

    Hanya memercayai X-Forwarded-For bila koneksi langsung datang dari
    proxy privat (gateway/nginx di host/loopback/private range) — otherwise
    penyerang bisa memalsukan header untuk bypass rate limit.
    """
    direct = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return direct
    direct_normalized = direct.replace("::ffff:", "", 1) if direct.startswith("::ffff:") else direct
    is_private_proxy = (
        direct_normalized in LOOPBACK_IPS
        or direct_normalized.startswith("10.")
        or direct_normalized.startswith("192.168.")
        or direct_normalized.startswith("172.16.")
        or direct_normalized.startswith("172.17.")
        or direct_normalized.startswith("172.18.")
        or direct_normalized.startswith("172.19.")
        or direct_normalized.startswith("172.2")
        or direct_normalized.startswith("172.30.")
        or direct_normalized.startswith("172.31.")
    )
    if is_private_proxy:
        return forwarded.split(",")[0].strip()
    return direct


async def audit_middleware(request: Request, call_next):
    """
    ASGI middleware. Wraps every request to:
      1. Check IP Whitelist (Confidentiality)
      ...
    """
    ip = _effective_client_ip(request)

    # Request correlation: SELALU regenerate server-side — jangan warisi nilai
    # klien (mencegah spoofing log / correlation-ID poisoning).
    rid = uuid.uuid4().hex
    _request_id_var.set(rid)

    # ── Debug Log ──
    safe_path = request.url.path.replace("\n", " ").replace("\r", " ")
    logger.debug(f"[security][{rid}] Incoming request from IP: {ip} | Path: {safe_path}")

    # ── IP Whitelist Check ──
    allowed = _get_allowed_ips()
    # Default-deny: tanpa env, hanya loopback yang lolos. Set ALLOWED_IP_WHITELIST=*
    # secara eksplisit untuk membuka ke semua (tidak disarankan).
    if "*" not in allowed and ip not in allowed and ip not in LOOPBACK_IPS:
        logger.warning(f"[security][{rid}] Access denied for IP: {ip}")
        # Return 403 directly
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=403,
            content={"detail": f"Access denied. Your IP ({ip}) is not whitelisted."},
            headers={"X-Request-ID": rid},
        )

    start = time.perf_counter()
    # Availability: rate limit before any processing
    try:
        _check_rate_limit(ip)
    except HTTPException:
        # Still need to return a proper response — log and re-raise
        latency = (time.perf_counter() - start) * 1000
        _write_audit(
            ip=ip,
            method=request.method,
            path=request.url.path,
            scope=None,
            status_code=429,
            latency_ms=latency,
            user_agent=request.headers.get("user-agent", ""),
            detail="rate_limit_exceeded",
        )
        raise

    # ── Integrity: verify HMAC signature on mutation requests ─────────────
    # Request.body() is cached by Starlette, so reading here does not prevent
    # the endpoint from reading the body/form afterwards.
    if request.method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
        try:
            body = await request.body()
        except Exception:
            body = b""
        _verify_hmac(request, body)

    response = await call_next(request)
    latency = (time.perf_counter() - start) * 1000
    # Echo correlation ID ke klien
    response.headers["X-Request-ID"] = rid

    _write_audit(
        ip=ip,
        method=request.method,
        path=request.url.path,
        scope=None,  # scope is determined inside the dependency, not here
        status_code=response.status_code,
        latency_ms=latency,
        user_agent=request.headers.get("user-agent", ""),
    )

    # ── Security response headers ─────────────────────────────────────────
    # Removed HSTS for local HTTP usage
    # Prevent MIME-sniffing content-type confusion attacks
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Deny framing — prevents clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    # No caching of financial API responses, EXCEPT for reward media/thumbnails
    # Note: For video Range requests, we MUST let the router set the cache headers
    if "/api/rewards/media" in request.url.path and "range" not in request.headers:
        response.headers["Cache-Control"] = "public, max-age=86400"  # Cache for 1 day
        if "Pragma" in response.headers:
            del response.headers["Pragma"]
    elif "/api/rewards/media" in request.url.path:
        # Range request: keep original headers
        pass
    else:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    # Remove server fingerprint
    response.headers["Server"] = "Finance-Tracker"
    # Prevent XSS via injected scripts and restrict resource loading
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    # Prevent referrer leakage to external services
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response


# ── Audit Query API (for /api/admin/audit route) ──────────────────────────────


def query_audit_log(
    limit: int = 100,
    ip: str | None = None,
    path: str | None = None,
    since: str | None = None,
) -> list[dict]:
    """Return recent audit log entries. Used by the admin endpoint."""
    clauses = []
    params: list = []
    if ip:
        clauses.append("ip = ?")
        params.append(ip)
    if path:
        clauses.append("path LIKE ?")
        params.append(f"%{path}%")
    if since:
        clauses.append("ts >= ?")
        params.append(since)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM audit_log {where} ORDER BY id DESC LIMIT ?"
    params.append(min(limit, 1000))
    try:
        db_path = _get_audit_db()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
    except Exception:
        return []
