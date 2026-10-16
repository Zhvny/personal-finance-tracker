import os
from unittest.mock import patch

import pytest

from services.runtime.vault_client import get_secret


def test_vault_disabled_without_addr(monkeypatch):
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    with pytest.raises(RuntimeError, match="vault unavailable"):
        get_secret("secret/alpha/test")


def test_vault_down_raises_not_fail_open(monkeypatch):
    monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
    with (
        patch("services.runtime.vault_client._headers", return_value={}),
        patch("services.runtime.vault_client.httpx.get", side_effect=Exception("conn refused")),
        pytest.raises(RuntimeError, match="vault unavailable"),
    ):
        get_secret("secret/alpha/test")


@patch("services.runtime.vault_client.httpx.get")
def test_vault_reads_secret(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"data": {"key": "value"}}
    with (
        patch.dict(os.environ, {"VAULT_ADDR": "http://vault:8200"}),
        patch("services.runtime.vault_client._headers", return_value={}),
    ):
        result = get_secret("secret/alpha/test")
    assert result == {"key": "value"}
    mock_get.assert_called_once()
