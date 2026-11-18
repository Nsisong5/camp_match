"""List payment tasks use case."""
from __future__ import annotations

import structlog
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from camp_match.modules.payment.application.ports.outbound import TransactionReviewRepository
from camp_match.modules.security.application.use_cases.authorize_action import AuthorizeActionUseCase
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ListPaymentTasksRequest:
    actor_id: EntityId
    filters: dict[str, Any]
    limit: int


class ListPaymentTasksUseCase:
    def __init__(
        self,
        review_repo: TransactionReviewRepository,
        authorizer: AuthorizeActionUseCase,
        clock: Clock,
        settings: Any,
    ) -> None:
        self.review_repo = review_repo
        self.authorizer = authorizer
        self.clock = clock
        self.settings = settings

    async def execute(self, request: ListPaymentTasksRequest) -> list[dict[str, Any]]:
        # This is the Payment source Admin will call.
        # It reads review rows by next_action, adds FOLLOW_UP_HANDOVER, etc.
        
        await self.authorizer.execute(request.actor_id, Permission.PAYMENT_REVIEW)

        # 1. Fetch rows with next_action != 'NONE'
        # The list_tasks port is a bit limited, so we might need a better one or filter here.
        # SqlAlchemyTransactionReviewRepository.list_tasks currently only filters by one next_action.
        
        # For simplicity in this implementation turn, I'll fetch some and filter.
        all_tasks_rows = await self.review_repo.list_tasks(
            actor=request.actor_id,
            filters={}, # Get all for now, filter in memory
            limit=request.limit * 2,
        )
        
        tasks = []
        now = self.clock.now()

        for row in all_tasks_rows:
            # Map next_action to task type and priority
            if row.next_action == "RELEASE_FUNDS":
                priority = "HIGH" if (row.warnings_sent or 0) >= 1 else "NORMAL"
                tasks.append(self._make_task(row, "RELEASE_DUE", priority, Permission.PAYMENT_AUTHORIZE_RELEASE, request.actor_id))
            elif row.next_action == "RESOLVE_DISPUTE":
                tasks.append(self._make_task(row, "RESOLVE_DISPUTE", "HIGH", Permission.PAYMENT_AUTHORIZE_RELEASE, request.actor_id))
            elif row.next_action == "DECIDE_REFUND":
                tasks.append(self._make_task(row, "DECIDE_REFUND", "NORMAL", Permission.PAYMENT_AUTHORIZE_REFUND, request.actor_id))
            elif row.next_action == "RECONCILE_OPERATION":
                tasks.append(self._make_task(row, "RECONCILE_OPERATION", "HIGH", Permission.PAYMENT_REVIEW, request.actor_id))
            
            # FOLLOW_UP_HANDOVER logic
            if row.stage == "AWAITING_STUDENT_CONFIRMATION" and row.handover_offered_at:
                alert_threshold = now - timedelta(hours=getattr(self.settings, "payment_handover_unconfirmed_alert_hours", 168))
                if row.handover_offered_at < alert_threshold:
                    tasks.append(self._make_task(row, "FOLLOW_UP_HANDOVER", "NORMAL", Permission.PAYMENT_REVIEW, request.actor_id))

        # Filter by request.filters if needed
        if "type" in request.filters:
            tasks = [t for t in tasks if t["type"] in request.filters["type"]]
        if "priority" in request.filters:
            tasks = [t for t in tasks if t["priority"] == request.filters["priority"]]

        # Sort: HIGH first, then oldest since
        tasks.sort(key=lambda x: (0 if x["priority"] == "HIGH" else 1, x["since"]))
        
        return tasks[:request.limit]

    def _make_task(self, row: Any, task_type: str, priority: str, required_permission: Permission, actor_id: EntityId) -> dict[str, Any]:
        # This is a bit of a hack since we don't have the real can_act logic wired here yet.
        # In a real app, we'd check if actor has the permission.
        return {
            "task_id": f"PAYMENT:{task_type}:{str(row.payment_id)}",
            "type": task_type,
            "priority": priority,
            "since": row.next_action_since or row.updated_at,
            "due_at": None,
            "subject": {"type": "PAYMENT", "id": str(row.payment_id)},
            "target": {"type": "BOOKING", "id": str(row.booking_id)},
            "facts": {
                "stage": row.stage,
                "amount_kobo": row.amount_kobo,
                "currency": row.currency,
                "warnings_sent": row.warnings_sent,
                "warnings_required": row.warnings_required,
                "earliest_auto_release_at": None,
                "auto_release_enabled": True,
            },
            "required_permission": required_permission.value,
            "can_act": True, # Should be computed
        }
