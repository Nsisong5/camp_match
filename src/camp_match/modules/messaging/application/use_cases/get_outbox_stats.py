from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OutboxStats:
    pending: int
    oldest_pending_age_seconds: int | None


class GetOutboxStatsUseCase:
    def __init__(self, outbox_repo: Any, clock: Any) -> None:
        self._outbox_repo = outbox_repo
        self._clock = clock

    async def execute(self) -> OutboxStats:
        pending, oldest_age = await self._outbox_repo.get_outbox_stats(self._clock)
        return OutboxStats(pending=pending, oldest_pending_age_seconds=oldest_age)
