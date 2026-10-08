from __future__ import annotations

from camp_match.modules.verification.application.errors import (
    VerificationCaseNotFound,
    EvidenceNotFound,
    VerificationForbiddenError,
)
from camp_match.modules.verification.application.ports.inbound import (
    GetEvidenceAccessRequest,
)
from camp_match.modules.verification.application.ports.outbound import (
    AccessGrant,
    EvidenceRepository,
    HistoryRepository,
    InspectionRepository,
    MediaProvider,
    VerificationCaseRepository,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork


class GetEvidenceAccessUseCase:
    def __init__(
        self,
        case_repo: VerificationCaseRepository,
        evidence_repo: EvidenceRepository,
        inspection_repo: InspectionRepository,
        history_repo: HistoryRepository,
        media_provider: MediaProvider,
        uow: UnitOfWork,
        is_reviewer: bool = False,
    ):
        self.case_repo = case_repo
        self.evidence_repo = evidence_repo
        self.inspection_repo = inspection_repo
        self.history_repo = history_repo
        self.media_provider = media_provider
        self.uow = uow
        self.is_reviewer = is_reviewer

    async def execute(self, request: GetEvidenceAccessRequest) -> AccessGrant:
        evidence = await self.evidence_repo.get_by_id(request.evidence_id)
        if not evidence:
            raise EvidenceNotFound()

        case = await self.case_repo.get_by_id(evidence.verification_case_id)
        if not case:
            raise VerificationCaseNotFound()

        active_inspection = await self.inspection_repo.get_active_by_case_id(case.id)

        is_owner = request.caller_id == case.submitted_by
        is_assigned_inspector = (
            active_inspection is not None
            and active_inspection.inspector_id == request.caller_id
        )

        if not is_owner and not is_assigned_inspector and not self.is_reviewer:
            raise VerificationForbiddenError("Caller not authorized to access evidence.")

        grant = await self.media_provider.get_access(evidence.media_id)

        async with self.uow:
            await self.history_repo.add(
                case_id=case.id,
                event_type="evidence_accessed",
                actor_id=request.caller_id,
                details=f"Evidence {evidence.id} accessed",
            )
            await self.uow.commit()

        return grant
