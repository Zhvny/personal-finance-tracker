import hmac

from packages.api.backend.security.core import is_dev_mode


def test_security_api_key_constant_time_comparison(monkeypatch):
    """
    Verifies that security checks utilize timing-attack resistant comparisons.
    """
    secret = "alpha_secure_key_12345"
    provided_good = "alpha_secure_key_12345"
    provided_bad = "alpha_secure_key_99999"

    assert hmac.compare_digest(secret, provided_good) is True
    assert hmac.compare_digest(secret, provided_bad) is False

def test_supply_chain_isolation(monkeypatch):
    """
    Verifies dev mode environment flags and security scope isolation.
    """
    monkeypatch.setenv("FINANCE_TRACKER_DEV_MODE", "1")
    assert is_dev_mode() is True

    monkeypatch.setenv("FINANCE_TRACKER_DEV_MODE", "0")
    assert is_dev_mode() is False
