"""Verification task source adapter."""
from __future__ import annotations

from typing import Any
from camp_match.modules.admin_operations.application.ports.outbound import (
    TaskItem,
    TaskSection,
    TaskSource,
)
from camp_match.modules.verification.application.ports.inbound import (
    ListPendingReviews,
    ListPendingReviewsRequest,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


class VerificationTaskSource(TaskSource):
    def __init__(self, list_pending_reviews_uc: ListPendingReviews, clock: Any) -> None:
        self._list_pending_reviews_uc = list_pending_reviews_uc
        self._clock = clock

    async def fetch(
        self, actor_id: EntityId, filters: dict[str, Any], limit: int
    ) -> TaskSection:
        # Note: ListPendingReviews doesn't seem to support limit/filters in its current port.
        # It returns list[Any].
        cases = await self._list_pending_reviews_uc.execute(
            ListPendingReviewsRequest(caller_id=actor_id)
        )

        items = []
        for case in cases:
            # We assume 'case' has relevant fields or we'd need a more specific DTO.
            case_id = getattr(case, "id", None) or getattr(case, "case_id", None)
            items.append(
                TaskItem(
                    task_id=f"VERIFICATION:REVIEW_PENDING:{str(case_id.value if case_id else 'unknown')}",
                    type="REVIEW_PENDING",
                    priority="NORMAL",
                    since=getattr(case, "created_at", self._clock.now()),
                    subject={"type": "VERIFICATION_CASE", "id": str(case_id.value if case_id else 'unknown')},
                    target={"type": "VERIFICATION_CASE", "id": str(case_id.value if case_id else 'unknown')},
                    facts={
                        "target_type": getattr(case, "target_type", "unknown"),
                    },
                    required_permission="VERIFICATION_REVIEW", # Placeholder
                    can_act=True,
                )
            )

        return TaskSection(
            source="VERIFICATION",
            status="OK",
            as_of=self._clock.now(),
            items=items[:limit],
            total=len(items),
        )
