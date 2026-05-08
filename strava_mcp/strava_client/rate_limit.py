import asyncio
import time
from collections import deque


class RateLimiter:
    """Enforces Strava's two-tier rate limits: 200 req/15 min and 2000 req/day."""

    def __init__(self, per_15min: int = 200, per_day: int = 2000) -> None:
        self._per_15min = per_15min
        self._per_day = per_day
        self._window_15min: deque[float] = deque()
        self._window_day: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._prune(now)

            if len(self._window_15min) >= self._per_15min:
                wait = self._window_15min[0] + 15 * 60 - now
                if wait > 0:
                    await asyncio.sleep(wait)
                    now = time.monotonic()
                    self._prune(now)

            if len(self._window_day) >= self._per_day:
                wait = self._window_day[0] + 24 * 3600 - now
                if wait > 0:
                    await asyncio.sleep(wait)
                    now = time.monotonic()
                    self._prune(now)

            self._window_15min.append(now)
            self._window_day.append(now)

    def _prune(self, now: float) -> None:
        cutoff_15min = now - 15 * 60
        cutoff_day = now - 24 * 3600
        while self._window_15min and self._window_15min[0] < cutoff_15min:
            self._window_15min.popleft()
        while self._window_day and self._window_day[0] < cutoff_day:
            self._window_day.popleft()
