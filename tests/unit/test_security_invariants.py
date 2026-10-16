import os

os.environ["SECRET_KEY"] = "test-secret-key-override"
os.environ["DEBUG"] = "True"
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_default_secret_detection_production():
    """
    Kontrak baru: tanpa SECRET_KEY (dan bukan mode TESTING/DEBUG), start gagal cepat.
    Tidak ada default key di source. Validasi diuji langsung via fungsi murni.
    """
    from apps.api.config import Settings, validate_security_settings

    with patch.dict(os.environ, {"SECRET_KEY": "", "DATABASE_URL": "", "DEBUG": "False", "TESTING": "False"}, clear=False):
        settings = Settings()
        with pytest.raises(RuntimeError, match="SECRET_KEY is not set"):
            validate_security_settings(settings)

    # DATABASE_URL kosong juga ditolak bila DEBUG off.
    with patch.dict(os.environ, {"SECRET_KEY": "x" * 32, "DATABASE_URL": "", "DEBUG": "False", "TESTING": "False"}, clear=False):
        settings = Settings()
        with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
            validate_security_settings(settings)

    # DEBUG=True: DATABASE_URL boleh kosong (dev lokal).
    with patch.dict(os.environ, {"SECRET_KEY": "x" * 32, "DATABASE_URL": "", "DEBUG": "True", "TESTING": "False"}, clear=False):
        settings = Settings()
        validate_security_settings(settings)  # tidak raise

def test_dev_mode_bypass_auth_when_production():
    """
    DEV mode cannot bypass auth when ENV is production.
    """
    from packages.api.backend.security.core import is_dev_mode
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "FINANCE_TRACKER_DEV_MODE": "1"}):
        assert is_dev_mode() is False

def test_dev_mode_bypass_auth_when_dev():
    """
    DEV mode works when not in production.
    """
    from packages.api.backend.security.core import is_dev_mode
    with patch.dict(os.environ, {"ENVIRONMENT": "development", "FINANCE_TRACKER_DEV_MODE": "1"}):
        assert is_dev_mode() is True

@pytest.mark.asyncio
async def test_invalid_api_key_rejected():
    """
    Invalid API key rejected with 401/403.
    """
    from fastapi import HTTPException

    from packages.api.backend.security.core import verify_api_key

    with patch("packages.api.backend.security.core._is_dev_mode", return_value=False), \
         patch("packages.api.backend.security.core._get_api_key", return_value="real-secret-key"):

        with pytest.raises(HTTPException) as excinfo:
            await verify_api_key("wrong-secret-key")
        assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_forged_user_prefix_token_is_rejected():
    """A token prefix is not proof of an authenticated server-side session."""
    from fastapi import HTTPException

    from packages.api.backend.security.core import verify_api_key

    with patch("packages.api.backend.security.core._is_dev_mode", return_value=False), \
         patch("packages.api.backend.security.core._get_api_key", return_value="real-secret-key"):
        with pytest.raises(HTTPException) as excinfo:
            await verify_api_key("user_attacker")
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_dev_mode_bypass_is_limited_to_loopback_clients():
    from fastapi import HTTPException

    from packages.api.backend.security.core import verify_api_key

    request = MagicMock()
    request.client.host = "203.0.113.20"
    with patch("packages.api.backend.security.core._is_dev_mode", return_value=True):
        with pytest.raises(HTTPException) as excinfo:
            await verify_api_key(None, request)
    assert excinfo.value.status_code == 403

@pytest.mark.asyncio
async def test_scope_authorization():
    """
    Scopes ("read", "write", "admin") are strictly enforced.
    """
    from fastapi import HTTPException

    from packages.api.backend.security.core import require_scope

    # Test that require_scope("admin") returns a dependency that raises 403 when token has "read"
    with patch("packages.api.backend.security.core._token_scope", return_value="read"):
        dep = require_scope("admin")
        with pytest.raises(HTTPException) as excinfo:
            await dep("some-token")
        assert excinfo.value.status_code == 403
        assert "Insufficient scope" in excinfo.value.detail

@pytest.mark.asyncio
async def test_stack_traces_suppressed_on_errors():
    """
    Stack traces are not returned to clients on errors (returns generic detail).
    """
    import json
    from unittest.mock import MagicMock

    from fastapi import Request

    from apps.api.main import create_app

    app = create_app()
    handler = app.exception_handlers.get(Exception)

    request = MagicMock(spec=Request)
    request.url.path = "/test"

    exc = ValueError("Secret stack trace")
    response = await handler(request, exc)

    assert response.status_code == 500
    body = json.loads(response.body.decode())
    assert "Secret stack trace" not in body.get("detail", "")
    assert body.get("detail") == "Internal Server Error"

def test_profile_name_validation_sql_injection():
    """
    Malformed profile identifiers (e.g. SQL injection attempts like `profile; DROP TABLE...`) 
    are rejected by profile validator/schema initializer.
    """
    from packages.core.application.profile_service import ProfileService

    service = ProfileService(Path("/tmp"))

    with pytest.raises(ValueError, match="Invalid profile name"):
        service.add_profile("profile; DROP TABLE users;")

    with pytest.raises(ValueError, match="Invalid profile name"):
        service.add_profile("' OR 1=1 --")
