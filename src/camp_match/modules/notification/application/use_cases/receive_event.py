"""Receive event use case."""
from __future__ import annotations

import structlog

from camp_match.modules.notification.application.ports.inbound import (
    ReceiveEventRequest,
)
from camp_match.modules.notification.application.ports.outbound import (
    InboxRepository,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock

logger = structlog.get_logger()


class ReceiveEventUseCase:
    def __init__(
        self, inbox_repo: InboxRepository, uow: UnitOfWork, clock: Clock
    ) -> None:
        self.inbox_repo = inbox_repo
        self.uow = uow
        self.clock = clock

    async def execute(self, request: ReceiveEventRequest) -> bool:
        now = self.clock.now()
        async with self.uow:
            inserted = await self.inbox_repo.add(
                request.event_id, request.event_type, request.payload, now
            )
            await self.uow.commit()

        if inserted:
            logger.info(
                "notification_event_received",
                event_id=request.event_id,
                event_type=request.event_type,
            )
        else:
            logger.info("notification_event_duplicate", event_id=request.event_id)

        return inserted
