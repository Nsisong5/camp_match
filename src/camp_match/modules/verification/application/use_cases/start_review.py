from __future__ import annotations

from camp_match.modules.verification.application.errors import VerificationCaseNotFound
from camp_match.modules.verification.application.ports.inbound import StartReviewRequest
from camp_match.modules.verification.application.ports.outbound import (
    HistoryRepository,
    VerificationCaseRepository,
)
from camp_match.modules.verification.domain.state_machine import transition
from camp_match.modules.verification.domain.value_objects import VerificationStatus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork


class StartReviewUseCase:
    def __init__(
        self,
        case_repo: VerificationCaseRepository,
        history_repo: HistoryRepository,
        uow: UnitOfWork,
    ):
        self.case_repo = case_repo
        self.history_repo = history_repo
        self.uow = uow

    async def execute(self, request: StartReviewRequest) -> None:
        case = await self.case_repo.get_by_id(request.case_id)
        if not case:
            raise VerificationCaseNotFound()

        transition(case, VerificationStatus.UNDER_REVIEW)

        async with self.uow:
            await self.case_repo.update(case)
            await self.history_repo.add(
                case_id=case.id,
                event_type="review_started",
                actor_id=request.caller_id,
                details="Review started",
            )
            await self.uow.commit()
