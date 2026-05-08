import time

import pytest

from strava_mcp.strava_client.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_acquire_records_timestamps() -> None:
    limiter = RateLimiter(per_15min=100, per_day=1000)
    for _ in range(5):
        await limiter.acquire()
    assert len(limiter._window_15min) == 5
    assert len(limiter._window_day) == 5


@pytest.mark.asyncio
async def test_prune_removes_expired_15min_entries() -> None:
    limiter = RateLimiter(per_15min=100, per_day=1000)
    limiter._window_15min.append(time.monotonic() - 16 * 60)
    await limiter.acquire()
    # old entry pruned, only the new one remains
    assert len(limiter._window_15min) == 1


@pytest.mark.asyncio
async def test_prune_removes_expired_day_entries() -> None:
    limiter = RateLimiter(per_15min=100, per_day=1000)
    limiter._window_day.append(time.monotonic() - 25 * 3600)
    await limiter.acquire()
    assert len(limiter._window_day) == 1


@pytest.mark.asyncio
async def test_recent_entries_not_pruned() -> None:
    limiter = RateLimiter(per_15min=100, per_day=1000)
    limiter._window_15min.append(time.monotonic() - 5 * 60)
    await limiter.acquire()
    assert len(limiter._window_15min) == 2
