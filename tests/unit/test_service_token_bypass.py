"""Service-token IP-bypass helper: authenticated internal callers skip the
IP deny-list, everyone else (and misconfiguration) fails closed."""

import os
from types import SimpleNamespace

import pytest

from packages.api.backend.security.core import _request_has_valid_service_token


def _req(token):
    headers = {} if token is None else {"x-service-token": token}
    return SimpleNamespace(headers=headers)


@pytest.fixture
def _clean_env(monkeypatch):
    monkeypatch.delenv("ALPHA_SERVICE_TOKEN", raising=False)


def test_no_header_denied(_clean_env, monkeypatch):
    monkeypatch.setenv("ALPHA_SERVICE_TOKEN", "s3cret")
    assert _request_has_valid_service_token(_req(None)) is False


def test_wrong_token_denied(_clean_env, monkeypatch):
    monkeypatch.setenv("ALPHA_SERVICE_TOKEN", "s3cret")
    assert _request_has_valid_service_token(_req("wrong")) is False


def test_correct_token_allowed(_clean_env, monkeypatch):
    monkeypatch.setenv("ALPHA_SERVICE_TOKEN", "s3cret")
    assert _request_has_valid_service_token(_req("s3cret")) is True


def test_unset_env_fails_closed_without_minting(_clean_env):
    assert _request_has_valid_service_token(_req("s3cret")) is False
    assert "ALPHA_SERVICE_TOKEN" not in os.environ


def test_surrounding_whitespace_trimmed(_clean_env, monkeypatch):
    monkeypatch.setenv("ALPHA_SERVICE_TOKEN", "  s3cret\n")
    assert _request_has_valid_service_token(_req("s3cret")) is True
