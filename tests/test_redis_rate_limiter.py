from unittest.mock import AsyncMock, patch

import pytest

from services.runtime.redis_rate_limiter import (
    _RATE_LIMIT,
    _RateLimitExceeded,
    _int_env,
    check_rate_limit,
)


@pytest.fixture(autouse=True)
def _mock_redis_env(monkeypatch):
    monkeypatch.setenv("ALPHA_REDIS_URL", "redis://localhost:6379/0")


@pytest.mark.asyncio
async def test_allows_requests_under_limit():
    ip = "10.0.0.99"
    mock_conn = AsyncMock()
    mock_conn.incr.return_value = 1
    with patch(
        "services.runtime.redis_rate_limiter.aioredis.Redis",
        return_value=mock_conn,
    ):
        for _ in range(5):
            await check_rate_limit(ip)
        assert mock_conn.incr.call_count == 5


@pytest.mark.asyncio
async def test_blocks_over_limit():
    ip = "10.0.1.77"
    mock_conn = AsyncMock()
    mock_conn.incr.side_effect = [1] * _RATE_LIMIT + [_RATE_LIMIT + 1]
    with patch(
        "services.runtime.redis_rate_limiter.aioredis.Redis",
        return_value=mock_conn,
    ):
        for _ in range(_RATE_LIMIT):
            await check_rate_limit(ip)
        with pytest.raises(_RateLimitExceeded):
            await check_rate_limit(ip)


def test_int_env_non_numeric_returns_default(monkeypatch):
    monkeypatch.setenv("ALPHA_GATEWAY_RATE_LIMIT", "abc")
    import services.runtime.redis_rate_limiter as rl

    assert rl._int_env("ALPHA_GATEWAY_RATE_LIMIT", 300) == 300
    assert _int_env("ALPHA_GATEWAY_RATE_LIMIT", 300) == 300
    assert _int_env("ALPHA_GATEWAY_RATE_LIMIT_MISSING_XYZ", 42) == 42
