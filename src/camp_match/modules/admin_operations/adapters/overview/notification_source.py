from __future__ import annotations

from typing import Any

from camp_match.modules.notification.application.ports.inbound import (
    GetInboxStatsRequest,
)
from camp_match.modules.notification.domain.value_objects import InboxStatus


class NotificationSourceAdapter:
    def __init__(self, get_inbox_stats_uc: Any) -> None:
        self._uc = get_inbox_stats_uc

    async def fetch(self) -> dict[str, Any]:
        stats = await self._uc.execute(GetInboxStatsRequest())
        pending = stats.get(InboxStatus.PENDING, 0)
        dead = stats.get(InboxStatus.DEAD, 0)
        return {"pending": pending, "dead": dead}
