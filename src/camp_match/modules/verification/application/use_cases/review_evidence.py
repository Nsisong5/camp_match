from __future__ import annotations

from camp_match.modules.verification.application.errors import (
    VerificationCaseNotFound,
    EvidenceNotFound,
)
from camp_match.modules.verification.application.ports.inbound import (
    ReviewEvidenceRequest,
    ReviewEvidenceResponse,
)
from camp_match.modules.verification.application.ports.outbound import (
    EvidenceRepository,
    HistoryRepository,
    VerificationCaseRepository,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork


class ReviewEvidenceUseCase:
    def __init__(
        self,
        case_repo: VerificationCaseRepository,
        evidence_repo: EvidenceRepository,
        history_repo: HistoryRepository,
        uow: UnitOfWork,
    ):
        self.case_repo = case_repo
        self.evidence_repo = evidence_repo
        self.history_repo = history_repo
        self.uow = uow

    async def execute(self, request: ReviewEvidenceRequest) -> ReviewEvidenceResponse:
        evidence = await self.evidence_repo.get_by_id(request.evidence_id)
        if not evidence:
            raise EvidenceNotFound()

        case = await self.case_repo.get_by_id(evidence.verification_case_id)
        if not case:
            raise VerificationCaseNotFound()

        evidence.update_review(request.review_status, request.notes, case.status)

        async with self.uow:
            await self.evidence_repo.update(evidence)
            await self.history_repo.add(
                case_id=case.id,
                event_type="evidence_reviewed",
                actor_id=request.caller_id,
                details=f"Evidence {evidence.id} reviewed to {request.review_status.value}",
            )

        return ReviewEvidenceResponse(
            evidence_id=evidence.id,
            review_status=evidence.review_status,
        )
