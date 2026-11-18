"""Payment task source adapter."""
from __future__ import annotations

from typing import Any
from camp_match.modules.admin_operations.application.ports.outbound import (
    TaskItem,
    TaskSection,
    TaskSource,
)
from camp_match.modules.payment.application.use_cases.list_payment_tasks import (
    ListPaymentTasksRequest,
    ListPaymentTasksUseCase,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


class PaymentTaskSource(TaskSource):
    def __init__(self, list_payment_tasks_uc: ListPaymentTasksUseCase, clock: Any) -> None:
        self._list_payment_tasks_uc = list_payment_tasks_uc
        self._clock = clock

    async def fetch(
        self, actor_id: EntityId, filters: dict[str, Any], limit: int
    ) -> TaskSection:
        # Note: In a real app, this might need its own session if the use case
        # doesn't manage it. But Admin's GetTasks says "each source in its own session".
        # If the use case relies on a repo that needs a session, the factory
        # for this adapter should provide a session-bound use case.
        
        tasks_data = await self._list_payment_tasks_uc.execute(
            ListPaymentTasksRequest(
                actor_id=actor_id,
                filters=filters,
                limit=limit,
            )
        )

        items = [
            TaskItem(
                task_id=t["task_id"],
                type=t["type"],
                priority=t["priority"],
                since=t["since"],
                subject=t["subject"],
                target=t["target"],
                facts=t["facts"],
                required_permission=t["required_permission"],
                can_act=t["can_act"],
                due_at=t.get("due_at"),
            )
            for t in tasks_data
        ]

        return TaskSection(
            source="PAYMENT",
            status="OK",
            as_of=self._clock.now(),
            items=items,
            total=len(items), # Simplified
        )
