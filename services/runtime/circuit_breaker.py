from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

logger = logging.getLogger("alpha.circuit_breaker")


class CircuitOpen(Exception):
    pass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0

    _failure_count: int = field(default=0, repr=False)
    _opened_at: datetime | None = field(default=None, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def call(self, fn: Callable[[], Awaitable[Any]]) -> Any:
        async with self._lock:
            if self._opened_at is not None:
                if datetime.now() - self._opened_at > timedelta(seconds=self.recovery_timeout):
                    self._failure_count = 0
                    self._opened_at = None
                else:
                    logger.warning("circuit breaker open")
                    raise CircuitOpen()
        try:
            result = await fn()
        except Exception:
            async with self._lock:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._opened_at = datetime.now()
            raise
        else:
            async with self._lock:
                self._failure_count = 0
                self._opened_at = None
            return result
