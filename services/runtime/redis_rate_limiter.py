from __future__ import annotations

import logging
import os
import time
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger("alpha.rate_limiter")


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    if not raw or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        logger.warning(f"{name}={raw!r} is not numeric, using default {default}")
        return default


_RATE_LIMIT = _int_env("ALPHA_GATEWAY_RATE_LIMIT", 300)
_RATE_WINDOW_SECS = 60
LOOPBACK_IPS = {"127.0.0.1", "::1", "localhost", "testclient"}
LOOPBACK_RATE_LIMIT_MULTIPLIER = 2
_POOL: Optional[aioredis.ConnectionPool] = None


def _redis_url() -> str:
    return os.getenv("ALPHA_REDIS_URL", "") or os.getenv("REDIS_URL", "")


def get_pool() -> aioredis.ConnectionPool:
    global _POOL
    if _POOL is None:
        _POOL = aioredis.ConnectionPool.from_url(_redis_url(), decode_responses=True, max_connections=20)
    return _POOL


class _RateLimitExceeded(Exception):
    def __init__(self, retry_after: int, ip: str, limit: int) -> None:
        super().__init__(f"rate limit exceeded for {ip}")
        self.retry_after = retry_after
        self.ip = ip
        self.limit = limit


async def check_rate_limit(ip: str) -> None:
    if _RATE_LIMIT <= 0:
        return
    # Samakan gateway: loopback bypass diganti multiplier 2x.
    effective = _RATE_LIMIT * LOOPBACK_RATE_LIMIT_MULTIPLIER if ip in LOOPBACK_IPS else _RATE_LIMIT
    redis_url = _redis_url()
    if not redis_url:
        return
    key = f"rate:{ip}:{int(time.time() // _RATE_WINDOW_SECS)}"
    try:
        r = aioredis.Redis(connection_pool=get_pool())
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, _RATE_WINDOW_SECS + 1)
        if count > effective:
            retry_after = _RATE_WINDOW_SECS - int(time.time() % _RATE_WINDOW_SECS)
            raise _RateLimitExceeded(retry_after=retry_after, ip=ip, limit=effective)
    except _RateLimitExceeded:
        raise
    except Exception as e:
        logger.warning(f"rate limiter redis error: {e}")
