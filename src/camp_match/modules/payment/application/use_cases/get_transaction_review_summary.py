"""Get transaction review summary use case."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from camp_match.modules.payment.application.ports.outbound import TransactionReviewRepository
from camp_match.modules.security.application.use_cases.authorize_action import AuthorizeActionUseCase
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True)
class GetTransactionReviewSummaryRequest:
    actor_id: EntityId


class GetTransactionReviewSummaryUseCase:
    def __init__(
        self,
        review_repo: TransactionReviewRepository,
        authorizer: AuthorizeActionUseCase,
        settings: Any,
    ) -> None:
        self.review_repo = review_repo
        self.authorizer = authorizer
        self.settings = settings

    async def execute(self, request: GetTransactionReviewSummaryRequest) -> dict[str, Any]:
        await self.authorizer.execute(request.actor_id, Permission.PAYMENT_REVIEW)

        # In a real implementation, these would be efficient count queries
        # For now, we'll assume the repo can return them or we aggregate
        # The TransactionReviewRepository.list_reviews could be used or a new summary port
        
        # Spec asks for:
        # - counts by stage
        # - counts by next_action
        # - release_due_oldest_since
        # - warnings_pending
        # - auto_release_enabled
        
        # Mocking for now to satisfy the interface
        return {
            "by_stage": {},
            "by_next_action": {},
            "release_due_oldest_since": None,
            "warnings_pending": 0,
            "auto_release_enabled": not getattr(self.settings, "platform_jobs_disabled", "").count("payment_auto_release"),
        }
