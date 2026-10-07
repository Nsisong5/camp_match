from __future__ import annotations

from camp_match.modules.verification.application.ports.inbound import ListMyVerificationCasesRequest
from camp_match.modules.verification.application.ports.outbound import VerificationCaseRepository


class ListMyVerificationCasesUseCase:
    def __init__(self, case_repo: VerificationCaseRepository):
        self.case_repo = case_repo

    async def execute(self, request: ListMyVerificationCasesRequest) -> list:
        return await self.case_repo.list_by_submitter(request.caller_id)
