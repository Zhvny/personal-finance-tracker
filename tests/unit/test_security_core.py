"""
TDD M4: Test untuk 3 critical untested functions di security/core.py:
  - _verify_hmac (HMAC integrity + anti-replay)
  - _check_rate_limit (sliding window per IP)
  - _write_audit (audit log persistence)

These were identified in M4 audit (2026-09-05) as high-severity gaps. Behavior
locked-in here. M4 juga rename _is_dev_mode/_get_api_key ke public name (C1 fix).

Test isolation:
  - HMAC tests: MagicMock Request, env override
  - Rate limit: reset module-level _rate_window antara test
  - Audit log: monkeypatch _AUDIT_DB ke tmp_path
"""
import hashlib
import hmac
import sqlite3
import time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from packages.api.backend.security import core as sec


# ═════════════════════════════════════════════════════════════════════════════
# § _verify_hmac
# ═════════════════════════════════════════════════════════════════════════════

def _make_request(method: str, path: str, headers: dict | None = None) -> MagicMock:
    """Helper: build a MagicMock mimicking FastAPI Request."""
    req = MagicMock()
    req.method = method
    req.url.path = path
    req.headers = headers or {}
    return req


def test_verify_hmac_passes_with_valid_signature(monkeypatch):
    """Valid signature + fresh timestamp + matching key → no exception."""
    monkeypatch.setenv("FINANCE_TRACKER_API_KEY", "test-secret-key")
    monkeypatch.delenv("FINANCE_TRACKER_HMAC_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")  # not production

    method, path, body = "POST", "/api/test", b'{"a":1}'
    ts = str(int(time.time()))
    key = "test-secret-key"
    canonical = f"{method}|{path}|{ts}|".encode() + body
    sig = hmac.new(key.encode(), canonical, hashlib.sha256).hexdigest()

    req = _make_request(method, path, {
        "X-Request-Signature": f"sha256={sig}",
        "X-Request-Timestamp": ts,
    })
    sec._verify_hmac(req, body)  # must not raise


def test_verify_hmac_rejects_mismatched_signature(monkeypatch):
    """Wrong signature → HTTP 403."""
    monkeypatch.setenv("FINANCE_TRACKER_API_KEY", "test-secret-key")
    monkeypatch.setenv("ENVIRONMENT", "development")

    ts = str(int(time.time()))
    req = _make_request("POST", "/api/test", {
        "X-Request-Signature": "sha256=" + "0" * 64,
        "X-Request-Timestamp": ts,
    })
    with pytest.raises(HTTPException) as exc:
        sec._verify_hmac(req, b"")
    assert exc.value.status_code == 403


def test_verify_hmac_rejects_stale_timestamp(monkeypatch):
    """Timestamp drift > 300s → HTTP 403 (replay suspected)."""
    monkeypatch.setenv("FINANCE_TRACKER_API_KEY", "test-secret-key")
    monkeypatch.setenv("ENVIRONMENT", "development")

    stale_ts = str(int(time.time()) - 600)  # 10 minutes ago
    key = "test-secret-key"
    canonical = f"POST|/api/test|{stale_ts}|".encode() + b""
    sig = hmac.new(key.encode(), canonical, hashlib.sha256).hexdigest()

    req = _make_request("POST", "/api/test", {
        "X-Request-Signature": f"sha256={sig}",
        "X-Request-Timestamp": stale_ts,
    })
    with pytest.raises(HTTPException) as exc:
        sec._verify_hmac(req, b"")
    assert exc.value.status_code == 403
    assert "replay" in exc.value.detail.lower()


def test_verify_hmac_rejects_missing_sha256_prefix(monkeypatch):
    """Signature without 'sha256=' prefix → HTTP 400."""
    monkeypatch.setenv("FINANCE_TRACKER_API_KEY", "test-secret-key")
    monkeypatch.setenv("ENVIRONMENT", "development")

    ts = str(int(time.time()))
    req = _make_request("POST", "/api/test", {
        "X-Request-Signature": "no-prefix-here",
        "X-Request-Timestamp": ts,
    })
    with pytest.raises(HTTPException) as exc:
        sec._verify_hmac(req, b"")
    assert exc.value.status_code == 400
    assert "sha256=" in exc.value.detail


def test_verify_hmac_rejects_non_integer_timestamp(monkeypatch):
    """X-Request-Timestamp non-integer → HTTP 400."""
    monkeypatch.setenv("FINANCE_TRACKER_API_KEY", "test-secret-key")
    monkeypatch.setenv("ENVIRONMENT", "development")

    req = _make_request("POST", "/api/test", {
        "X-Request-Signature": "sha256=" + "0" * 64,
        "X-Request-Timestamp": "not-a-number",
    })
    with pytest.raises(HTTPException) as exc:
        sec._verify_hmac(req, b"")
    assert exc.value.status_code == 400
    assert "unix epoch" in exc.value.detail.lower()


def test_verify_hmac_production_requires_signature(monkeypatch):
    """Production + mutation + missing signature → HTTP 400."""
    monkeypatch.setenv("FINANCE_TRACKER_API_KEY", "test-secret-key")
    monkeypatch.setenv("ENVIRONMENT", "production")

    req = _make_request("POST", "/api/test", {})
    with pytest.raises(HTTPException) as exc:
        sec._verify_hmac(req, b"")
    assert exc.value.status_code == 400
    assert "required" in exc.value.detail.lower()


def test_verify_hmac_dev_mode_allows_missing_signature(monkeypatch):
    """Non-production + missing signature → silent return (optional)."""
    monkeypatch.setenv("FINANCE_TRACKER_API_KEY", "test-secret-key")
    monkeypatch.setenv("ENVIRONMENT", "development")

    req = _make_request("POST", "/api/test", {})
    # Should not raise — opt-in mode
    sec._verify_hmac(req, b"")


def test_verify_hmac_no_key_configured_silently_passes(monkeypatch):
    """No key configured (no API key, no HMAC key) + signature present → silent return."""
    monkeypatch.delenv("FINANCE_TRACKER_API_KEY", raising=False)
    monkeypatch.delenv("FINANCE_TRACKER_HMAC_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")

    req = _make_request("POST", "/api/test", {
        "X-Request-Signature": "sha256=" + "a" * 64,
        "X-Request-Timestamp": str(int(time.time())),
    })
    # Can't verify without key → silent return (line 234-235)
    sec._verify_hmac(req, b"")


# ═════════════════════════════════════════════════════════════════════════════
# § _check_rate_limit
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=False)
def reset_rate_window():
    """Clear module-level _rate_window between tests."""
    sec._rate_window.clear()
    yield
    sec._rate_window.clear()


def test_check_rate_limit_allows_below_limit(monkeypatch, reset_rate_window):
    """First N requests below limit → no exception."""
    monkeypatch.setenv("FINANCE_TRACKER_RATE_LIMIT", "5")
    monkeypatch.delenv("FINANCE_TRACKER_DEV_MODE", raising=False)
    for _ in range(5):
        sec._check_rate_limit("192.0.2.1")  # must not raise


def test_check_rate_limit_blocks_at_limit(monkeypatch, reset_rate_window):
    """Request beyond limit → HTTP 429."""
    monkeypatch.setenv("FINANCE_TRACKER_RATE_LIMIT", "3")
    monkeypatch.delenv("FINANCE_TRACKER_DEV_MODE", raising=False)

    for _ in range(3):
        sec._check_rate_limit("192.0.2.2")
    with pytest.raises(HTTPException) as exc:
        sec._check_rate_limit("192.0.2.2")
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


def test_check_rate_limit_per_ip_isolation(monkeypatch, reset_rate_window):
    """Different IPs tracked independently."""
    monkeypatch.setenv("FINANCE_TRACKER_RATE_LIMIT", "2")
    monkeypatch.delenv("FINANCE_TRACKER_DEV_MODE", raising=False)

    # IP1 maxed out
    for _ in range(2):
        sec._check_rate_limit("192.0.2.10")
    with pytest.raises(HTTPException):
        sec._check_rate_limit("192.0.2.10")

    # IP2 still allowed
    sec._check_rate_limit("192.0.2.20")
    sec._check_rate_limit("192.0.2.20")


def test_check_rate_limit_zero_disables(monkeypatch, reset_rate_window):
    """FINANCE_TRACKER_RATE_LIMIT=0 → unlimited (line 168-169 short-circuit)."""
    monkeypatch.setenv("FINANCE_TRACKER_RATE_LIMIT", "0")
    monkeypatch.delenv("FINANCE_TRACKER_DEV_MODE", raising=False)
    # Even 100 requests from same IP should pass
    for _ in range(100):
        sec._check_rate_limit("192.0.2.30")


def test_check_rate_limit_loopback_high_limit(monkeypatch, reset_rate_window):
    """Loopback IPs get 5000 req/min default (line 173)."""
    monkeypatch.delenv("FINANCE_TRACKER_RATE_LIMIT", raising=False)
    monkeypatch.delenv("FINANCE_TRACKER_DEV_MODE", raising=False)
    # 100 requests to loopback should not hit limit (limit = 5000)
    for _ in range(100):
        sec._check_rate_limit("127.0.0.1")


# ═════════════════════════════════════════════════════════════════════════════
# § _write_audit
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def audit_db(tmp_path, monkeypatch):
    """Redirect _AUDIT_DB to a tmp_path SQLite file + ensure schema."""
    db_path = str(tmp_path / "audit_test.db")
    monkeypatch.setattr(sec, "_AUDIT_DB", db_path)
    # Re-init schema for the test DB
    sec._init_audit_db()
    return db_path


def test_write_audit_persists_record(audit_db):
    """_write_audit INSERTs a row, retrievable via SELECT."""
    sec._write_audit(
        ip="192.0.2.1", method="GET", path="/api/test",
        scope="read", status_code=200, latency_ms=12.5,
        user_agent="test-agent/1.0", detail=None,
    )
    with sqlite3.connect(audit_db) as conn:
        rows = conn.execute("SELECT * FROM audit_log").fetchall()
    assert len(rows) == 1
    # Schema: (id, ts, ip, method, path, scope, status_code, latency_ms, user_agent, detail)
    ip, method, path, scope, status_code = rows[0][2:7]
    assert ip == "192.0.2.1"
    assert method == "GET"
    assert path == "/api/test"
    assert scope == "read"
    assert status_code == 200


def test_write_audit_user_agent_truncated_to_200(audit_db):
    """user_agent longer than 200 chars truncated (line 308-309)."""
    long_ua = "A" * 500
    sec._write_audit(
        ip="1.1.1.1", method="POST", path="/api/x",
        scope=None, status_code=403, latency_ms=1.0,
        user_agent=long_ua,
    )
    with sqlite3.connect(audit_db) as conn:
        row = conn.execute("SELECT user_agent FROM audit_log").fetchone()
    assert len(row[0]) == 200


def test_write_audit_latency_rounded_to_2_decimals(audit_db):
    """latency_ms rounded to 2 decimal places (line 311)."""
    sec._write_audit(
        ip="1.1.1.1", method="GET", path="/api/x",
        scope=None, status_code=200, latency_ms=12.3456789,
        user_agent="",
    )
    with sqlite3.connect(audit_db) as conn:
        row = conn.execute("SELECT latency_ms FROM audit_log").fetchone()
    assert row[0] == 12.35


def test_write_audit_never_raises_on_failure(monkeypatch, tmp_path):
    """Audit failure must not break request flow (line 295 comment)."""
    # Point to a non-writable path to force sqlite3.connect failure
    bad_path = "/nonexistent_root_xyz_9999/db.db"
    monkeypatch.setattr(sec, "_AUDIT_DB", bad_path)
    # Should NOT raise — audit failure swallowed
    sec._write_audit(
        ip="1.1.1.1", method="GET", path="/api/x",
        scope=None, status_code=200, latency_ms=1.0,
        user_agent="",
    )


def test_write_audit_scope_and_detail_optional(audit_db):
    """scope and detail are optional (None allowed)."""
    sec._write_audit(
        ip="1.1.1.1", method="GET", path="/api/x",
        scope=None, status_code=200, latency_ms=1.0,
        user_agent="", detail=None,
    )
    with sqlite3.connect(audit_db) as conn:
        row = conn.execute("SELECT scope, detail FROM audit_log").fetchone()
    assert row == (None, None)


# ═════════════════════════════════════════════════════════════════════════════
# § Public API backward-compat (C1 fix verification)
# ═════════════════════════════════════════════════════════════════════════════

def test_public_aliases_match_private():
    """is_dev_mode / get_api_key are public; old _-prefixed names are aliases."""
    assert sec.is_dev_mode is sec._is_dev_mode
    assert sec.get_api_key is sec._get_api_key


def test_dev_mode_env_override(monkeypatch):
    """FINANCE_TRACKER_DEV_MODE=1 (non-prod) → is_dev_mode True."""
    monkeypatch.setenv("FINANCE_TRACKER_DEV_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert sec.is_dev_mode() is True


def test_dev_mode_production_override(monkeypatch):
    """FINANCE_TRACKER_DEV_MODE=1 + ENVIRONMENT=production → False (secure default)."""
    monkeypatch.setenv("FINANCE_TRACKER_DEV_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert sec.is_dev_mode() is False
