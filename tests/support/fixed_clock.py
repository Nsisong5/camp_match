"""Fixed clock test support."""

from datetime import datetime, timedelta


class FixedClock:
    def __init__(self, fixed_time: datetime) -> None:
        self._fixed_time = fixed_time

    def now(self) -> datetime:
        return self._fixed_time

    def advance(self, seconds: int = 1) -> None:
        self._fixed_time += timedelta(seconds=seconds)
