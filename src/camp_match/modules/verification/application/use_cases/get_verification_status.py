from __future__ import annotations

from camp_match.modules.verification.application.ports.inbound import (
    GetVerificationStatusRequest,
    VerificationStatusResponse,
)
from camp_match.modules.verification.application.ports.outbound import (
    VerificationCaseRepository,
    VerificationDecisionRepository,
)


class GetVerificationStatusUseCase:
    def __init__(
        self,
        case_repo: VerificationCaseRepository,
        decision_repo: VerificationDecisionRepository,
    ):
        self.case_repo = case_repo
        self.decision_repo = decision_repo

    async def execute(self, request: GetVerificationStatusRequest) -> VerificationStatusResponse:
        latest_case = await self.case_repo.get_latest_by_target(request.target_type, request.target_id)
        if not latest_case:
            return VerificationStatusResponse(is_verified=False, verified_on=None)

        is_valid = latest_case.is_currently_valid()
        verified_on = None
        if is_valid:
            decision = await self.decision_repo.get_by_case_id(latest_case.id)
            if decision:
                verified_on = decision.decided_at.date()

        return VerificationStatusResponse(is_verified=is_valid, verified_on=verified_on)
