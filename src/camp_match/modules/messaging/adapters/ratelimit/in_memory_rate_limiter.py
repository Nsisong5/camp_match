from __future__ import annotations

import math
from typing import TYPE_CHECKING, Protocol

from camp_match.modules.messaging.application.ports.outbound import RateLimitResult
from camp_match.platform.clock import SystemClock

if TYPE_CHECKING:
    from datetime import datetime


class Clock(Protocol):
    def now(self) -> datetime:
        ...


class InMemoryRateLimiter:
    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock or SystemClock()
        self._windows: dict[str, list[float]] = {}

    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = self._clock.now().timestamp()
        window_start = now - window_seconds

        timestamps = self._windows.get(key, [])
        valid_timestamps = [t for t in timestamps if t > window_start]

        if not valid_timestamps:
            if key in self._windows:
                del self._windows[key]
        else:
            self._windows[key] = valid_timestamps

        current_count = len(self._windows.get(key, []))

        if current_count >= limit:
            oldest = self._windows[key][0]
            retry_after = int(math.ceil((oldest + window_seconds) - now))
            return RateLimitResult(allowed=False, retry_after_seconds=max(1, retry_after))

        self._windows.setdefault(key, []).append(now)
        return RateLimitResult(allowed=True, retry_after_seconds=0)
