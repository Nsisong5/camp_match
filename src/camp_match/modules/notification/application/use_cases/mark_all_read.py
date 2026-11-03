"""Mark all read use case."""
from __future__ import annotations

from camp_match.modules.notification.application.ports.inbound import (
    MarkAllReadRequest,
    MarkAllReadResult,
)
from camp_match.modules.notification.application.ports.outbound import (
    NotificationRepository,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock


class MarkAllReadUseCase:
    def __init__(
        self,
        notification_repo: NotificationRepository,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.notification_repo = notification_repo
        self.uow = uow
        self.clock = clock

    async def execute(self, request: MarkAllReadRequest) -> MarkAllReadResult:
        now = self.clock.now()
        async with self.uow:
            marked = await self.notification_repo.mark_all_read(
                request.actor_id, request.category, now
            )
            await self.uow.commit()
        return MarkAllReadResult(marked_read=marked)
