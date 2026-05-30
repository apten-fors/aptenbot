import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from utils.rate_limiter import InMemoryFixedWindowRateLimiter


@pytest.mark.asyncio
async def test_in_memory_allows_up_to_limit_then_blocks():
    limiter = InMemoryFixedWindowRateLimiter(limit=3, window_seconds=60)
    user_id = 123
    assert await limiter.allow(user_id) is True
    assert await limiter.allow(user_id) is True
    assert await limiter.allow(user_id) is True
    # 4th request within the window is blocked
    assert await limiter.allow(user_id) is False


@pytest.mark.asyncio
async def test_in_memory_is_per_user():
    limiter = InMemoryFixedWindowRateLimiter(limit=1, window_seconds=60)
    assert await limiter.allow(1) is True
    assert await limiter.allow(1) is False
    # Different caller has its own window
    assert await limiter.allow(2) is True


@pytest.mark.asyncio
async def test_in_memory_zero_limit_denies():
    limiter = InMemoryFixedWindowRateLimiter(limit=0, window_seconds=60)
    assert await limiter.allow(1) is False


@pytest.mark.asyncio
async def test_in_memory_window_expiry(monkeypatch):
    limiter = InMemoryFixedWindowRateLimiter(limit=1, window_seconds=60)
    times = [1000.0]
    monkeypatch.setattr("utils.rate_limiter.time.monotonic", lambda: times[0])

    assert await limiter.allow(1) is True
    assert await limiter.allow(1) is False
    # Advance beyond the window: the old hit is pruned
    times[0] = 1061.0
    assert await limiter.allow(1) is True
