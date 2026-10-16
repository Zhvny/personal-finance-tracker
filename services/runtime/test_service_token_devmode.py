"""Audit T3 (2026-09-02): Alpha DEV_MODE / service-token guards.

Verifies the ``should_require_service_token`` matrix:
- dev mode + loopback  -> bypass (return False) for dev convenience
- dev mode + non-loopback -> require
- production (any) -> always require
- no env (default off) -> always require
"""
from __future__ import annotations


import pytest


@pytest.fixture
def reload_token(monkeypatch):
    """Reload the module so module-level env reads pick up monkeypatch."""
    import sys

    for m in list(sys.modules):
        if m == "services.runtime.service_token":
            del sys.modules[m]
    yield
    for m in list(sys.modules):
        if m == "services.runtime.service_token":
            del sys.modules[m]


def test_production_always_requires(monkeypatch, reload_token):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("FINANCE_TRACKER_DEV_MODE", "1")
    from services.runtime.service_token import should_require_service_token

    assert should_require_service_token("127.0.0.1") is True
    assert should_require_service_token("8.8.8.8") is True


def test_dev_mode_loopback_bypass(monkeypatch, reload_token):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("FINANCE_TRACKER_DEV_MODE", "1")
    from services.runtime.service_token import should_require_service_token

    assert should_require_service_token("127.0.0.1") is False
    assert should_require_service_token("") is False  # unknown peer = loopback bucket


def test_dev_mode_remote_still_requires(monkeypatch, reload_token):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("FINANCE_TRACKER_DEV_MODE", "1")
    from services.runtime.service_token import should_require_service_token

    assert should_require_service_token("8.8.8.8") is True


def test_default_no_dev_mode_requires(monkeypatch, reload_token):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("FINANCE_TRACKER_DEV_MODE", raising=False)
    from services.runtime.service_token import should_require_service_token

    assert should_require_service_token("127.0.0.1") is True
    assert should_require_service_token("8.8.8.8") is True
