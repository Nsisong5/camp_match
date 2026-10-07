from __future__ import annotations

from camp_match.modules.verification.application.errors import VerificationForbiddenError
from camp_match.modules.verification.application.ports.inbound import ListPendingReviewsRequest
from camp_match.modules.verification.application.ports.outbound import VerificationCaseRepository


class ListPendingReviewsUseCase:
    def __init__(self, case_repo: VerificationCaseRepository, is_reviewer: bool = False):
        self.case_repo = case_repo
        self.is_reviewer = is_reviewer

    async def execute(self, request: ListPendingReviewsRequest) -> list:
        if not self.is_reviewer:
            raise VerificationForbiddenError("Only reviewers can list pending reviews.")
        return await self.case_repo.list_pending_review()
