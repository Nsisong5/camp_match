"""Get unread count use case."""
from __future__ import annotations

from camp_match.modules.notification.application.ports.inbound import (
    GetUnreadCountRequest,
    UnreadCountResult,
)
from camp_match.modules.notification.application.ports.outbound import (
    NotificationRepository,
)


class GetUnreadCountUseCase:
    def __init__(self, notification_repo: NotificationRepository) -> None:
        self.notification_repo = notification_repo

    async def execute(self, request: GetUnreadCountRequest) -> UnreadCountResult:
        count = await self.notification_repo.count_unread(request.actor_id)
        return UnreadCountResult(unread_count=count)
