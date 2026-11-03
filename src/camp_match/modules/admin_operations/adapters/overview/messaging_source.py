from __future__ import annotations

from typing import Any


class MessagingSourceAdapter:
    def __init__(self, get_outbox_stats_uc: Any) -> None:
        self._uc = get_outbox_stats_uc

    async def fetch(self) -> dict[str, Any]:
        stats = await self._uc.execute()
        return {
            "outbox_pending": stats.pending,
            "outbox_oldest_age_seconds": stats.oldest_pending_age_seconds,
        }
