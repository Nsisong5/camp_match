"""Get inbox stats use case."""
from __future__ import annotations

from camp_match.modules.notification.application.ports.inbound import (
    GetInboxStatsRequest,
)
from camp_match.modules.notification.application.ports.outbound import (
    InboxRepository,
)
from camp_match.modules.notification.domain.value_objects import InboxStatus


class GetInboxStatsUseCase:
    def __init__(self, inbox_repo: InboxRepository) -> None:
        self.inbox_repo = inbox_repo

    async def execute(
        self, request: GetInboxStatsRequest
    ) -> dict[InboxStatus, int]:
        return await self.inbox_repo.stats()
