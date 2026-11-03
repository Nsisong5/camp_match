"""Process pending inbox use case."""
from __future__ import annotations

from camp_match.modules.notification.application.ports.inbound import (
    ProcessInboxEventRequest,
    ProcessOutcome,
    ProcessPendingInboxRequest,
)
from camp_match.modules.notification.application.ports.outbound import (
    InboxRepository,
)
from camp_match.modules.notification.application.use_cases.process_inbox_event import (
    ProcessInboxEventUseCase,
)
from camp_match.shared_kernel.domain.clock import Clock


class ProcessPendingInboxUseCase:
    def __init__(
        self,
        inbox_repo: InboxRepository,
        process_event_use_case: ProcessInboxEventUseCase,
        clock: Clock,
    ) -> None:
        self.inbox_repo = inbox_repo
        self.process_event_use_case = process_event_use_case
        self.clock = clock

    async def execute(
        self, request: ProcessPendingInboxRequest
    ) -> dict[ProcessOutcome, int]:
        now = self.clock.now()
        due_ids = await self.inbox_repo.list_due(now, request.limit)
        counts = {st: 0 for st in ProcessOutcome}
        for event_id in due_ids:
            outcome = await self.process_event_use_case.execute(
                ProcessInboxEventRequest(event_id=event_id)
            )
            counts[outcome] += 1
        return counts
