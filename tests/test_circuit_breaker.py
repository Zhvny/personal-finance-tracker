import asyncio

import pytest

from services.runtime.circuit_breaker import CircuitBreaker, CircuitOpen


@pytest.mark.asyncio
async def test_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

    async def fail():
        raise ConnectionError("boom")

    for _ in range(3):
        with pytest.raises(ConnectionError):
            await cb.call(fail)
    with pytest.raises(CircuitOpen):
        await cb.call(fail)


@pytest.mark.asyncio
async def test_half_open_after_timeout():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

    async def fail():
        raise ConnectionError("boom")

    for _ in range(2):
        with pytest.raises(ConnectionError):
            await cb.call(fail)
    await asyncio.sleep(0.15)
    with pytest.raises(ConnectionError):
        await cb.call(fail)
