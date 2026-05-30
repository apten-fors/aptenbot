"""Rate limiting for Telegram Guest Mode requests.

A small interface (``GuestRateLimiter``) with two implementations:

  - ``InMemoryFixedWindowRateLimiter`` — per-process fixed window, no infra.
  - ``RedisFixedWindowRateLimiter`` — uses the existing ``RedisClient`` so the
    limit holds across restarts / multiple processes; degrades to an in-memory
    fallback on any Redis error.

``create_guest_rate_limiter`` picks Redis when it is configured and reachable,
otherwise in-memory. The interface is intentionally minimal (``async allow``)
so the implementation can be swapped without touching the router.
"""
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from utils.logging_config import logger
from utils.settings import REDIS_URL, REDIS_SENTINEL_HOSTS


class GuestRateLimiter:
    """Interface marker for guest rate limiters."""

    async def allow(self, caller_user_id: int) -> bool:  # pragma: no cover - interface
        raise NotImplementedError


class InMemoryFixedWindowRateLimiter(GuestRateLimiter):
    """Per-caller fixed-window limiter held in process memory.

    Single-process only (matches the current in-memory ``SessionManager`` and
    aiogram ``MemoryStorage``).
    """

    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window = window_seconds
        self._hits: Dict[int, Deque[float]] = defaultdict(deque)

    async def allow(self, caller_user_id: int) -> bool:
        if self.limit <= 0:
            return False
        now = time.monotonic()
        cutoff = now - self.window
        dq = self._hits[caller_user_id]
        while dq and dq[0] <= cutoff:
            dq.popleft()
        if len(dq) >= self.limit:
            return False
        dq.append(now)
        return True


class RedisFixedWindowRateLimiter(GuestRateLimiter):
    """Fixed-window limiter backed by Redis (key ``telegram:guest:rate:<id>``).

    Uses ``INCR`` + ``EXPIRE``. On any Redis error it falls back to an internal
    in-memory limiter so a Redis outage never blocks legitimate callers.
    """

    def __init__(self, redis_client, limit: int, window_seconds: int = 60):
        self.redis_client = redis_client
        self.limit = limit
        self.window = window_seconds
        self._fallback = InMemoryFixedWindowRateLimiter(limit, window_seconds)

    async def allow(self, caller_user_id: int) -> bool:
        if self.limit <= 0:
            return False
        key = f"telegram:guest:rate:{caller_user_id}"
        try:
            client = self.redis_client.get_master()
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, self.window)
            return count <= self.limit
        except Exception as e:  # noqa: BLE001 - degrade gracefully on any Redis error
            logger.warning("Guest rate limiter Redis error, using in-memory fallback: %s", e)
            return await self._fallback.allow(caller_user_id)


async def create_guest_rate_limiter(limit: int, window_seconds: int = 60) -> GuestRateLimiter:
    """Build the best available guest rate limiter.

    Prefers Redis when ``REDIS_URL`` or ``REDIS_SENTINEL_HOSTS`` is configured and
    a ping succeeds; otherwise falls back to an in-memory limiter.
    """
    if REDIS_URL or REDIS_SENTINEL_HOSTS:
        try:
            from utils.redis_client import RedisClient

            redis_client = RedisClient()
            if await redis_client.ping():
                logger.info("Guest rate limiter using Redis backend")
                return RedisFixedWindowRateLimiter(redis_client, limit, window_seconds)
            logger.warning("Guest rate limiter: Redis ping failed, using in-memory limiter")
        except Exception as e:  # noqa: BLE001
            logger.warning("Guest rate limiter: Redis unavailable (%s), using in-memory limiter", e)
    else:
        logger.info("Guest rate limiter using in-memory backend (Redis not configured)")
    return InMemoryFixedWindowRateLimiter(limit, window_seconds)
