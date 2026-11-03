from __future__ import annotations

from typing import Any

from camp_match.modules.notification.application.ports.inbound import (
    RequeueDeadEventsRequest,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessNotificationRecovery:
    def __init__(self, requeue_dead_uc: Any) -> None:
        self._uc = requeue_dead_uc

    async def requeue_dead(self, actor_id: EntityId) -> int:
        res = await self._uc.execute(RequeueDeadEventsRequest())
        return int(res) if isinstance(res, (int, float)) else 1
