"""Requeue dead events use case."""
from __future__ import annotations

from camp_match.modules.notification.application.ports.inbound import (
    RequeueDeadEventsRequest,
)
from camp_match.modules.notification.application.ports.outbound import (
    InboxRepository,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork


class RequeueDeadEventsUseCase:
    def __init__(self, inbox_repo: InboxRepository, uow: UnitOfWork) -> None:
        self.inbox_repo = inbox_repo
        self.uow = uow

    async def execute(self, request: RequeueDeadEventsRequest) -> int:
        async with self.uow:
            count = await self.inbox_repo.requeue_dead()
            await self.uow.commit()
        return count
