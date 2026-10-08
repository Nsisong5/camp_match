from __future__ import annotations

from camp_match.modules.verification.application.errors import (
    VerificationCaseNotFound,
    VerificationForbiddenError,
)
from camp_match.modules.verification.application.ports.inbound import (
    SubmitVerificationCaseRequest,
)
from camp_match.modules.verification.application.ports.outbound import (
    HistoryRepository,
    VerificationCaseRepository,
)
from camp_match.modules.verification.domain.state_machine import transition
from camp_match.modules.verification.domain.value_objects import VerificationStatus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork


class SubmitVerificationCaseUseCase:
    def __init__(
        self,
        case_repo: VerificationCaseRepository,
        history_repo: HistoryRepository,
        uow: UnitOfWork,
    ):
        self.case_repo = case_repo
        self.history_repo = history_repo
        self.uow = uow

    async def execute(self, request: SubmitVerificationCaseRequest) -> None:
        case = await self.case_repo.get_by_id(request.case_id)
        if not case:
            raise VerificationCaseNotFound()

        if request.caller_id != case.submitted_by:
            raise VerificationForbiddenError("Only the case submitter can submit this case.")

        transition(case, VerificationStatus.SUBMITTED)

        async with self.uow:
            await self.case_repo.update(case)
            await self.history_repo.add(
                case_id=case.id,
                event_type="verification_case_submitted",
                actor_id=request.caller_id,
                details="Verification case submitted",
            )
            await self.uow.commit()
