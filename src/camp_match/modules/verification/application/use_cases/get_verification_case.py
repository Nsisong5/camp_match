from __future__ import annotations

from camp_match.modules.verification.application.errors import (
    VerificationCaseNotFound,
    VerificationForbiddenError,
)
from camp_match.modules.verification.application.ports.inbound import (
    EvidenceOwnerDTO,
    EvidenceReviewerDTO,
    GetVerificationCaseRequest,
    VerificationCaseOwnerDTO,
    VerificationCaseReviewerDTO,
)
from camp_match.modules.verification.application.ports.outbound import (
    EvidenceRepository,
    HistoryRepository,
    InspectionRepository,
    VerificationCaseRepository,
)


class GetVerificationCaseUseCase:
    def __init__(
        self,
        case_repo: VerificationCaseRepository,
        evidence_repo: EvidenceRepository,
        inspection_repo: InspectionRepository,
        history_repo: HistoryRepository,
    ):
        self.case_repo = case_repo
        self.evidence_repo = evidence_repo
        self.inspection_repo = inspection_repo
        self.history_repo = history_repo

    async def execute(
        self, request: GetVerificationCaseRequest
    ) -> VerificationCaseOwnerDTO | VerificationCaseReviewerDTO:
        case = await self.case_repo.get_by_id(request.case_id)
        if not case:
            raise VerificationCaseNotFound()

        active_inspection = await self.inspection_repo.get_active_by_case_id(case.id)
        is_owner = request.caller_id == case.submitted_by
        is_inspector = active_inspection is not None and active_inspection.inspector_id == request.caller_id

        if not is_owner and not is_inspector and not request.is_reviewer:
            raise VerificationForbiddenError("Caller not authorized to view verification case.")

        evidence_list = await self.evidence_repo.list_by_case_id(case.id)

        if request.is_reviewer:
            history_list = await self.history_repo.list_by_case_id(case.id)
            return VerificationCaseReviewerDTO(
                id=case.id,
                target_type=case.target_type,
                target_id=case.target_id,
                status=case.status,
                submitted_by=case.submitted_by,
                expires_at=case.expires_at,
                evidence=[
                    EvidenceReviewerDTO(
                        id=e.id,
                        evidence_type=e.evidence_type,
                        media_id=e.media_id,
                        submitted_by=e.submitted_by,
                        source_description=e.source_description,
                        captured_at=e.captured_at,
                        review_status=e.review_status,
                        review_notes=e.review_notes,
                    )
                    for e in evidence_list
                ],
                history=history_list,
            )
        else:
            return VerificationCaseOwnerDTO(
                id=case.id,
                target_type=case.target_type,
                target_id=case.target_id,
                status=case.status,
                submitted_by=case.submitted_by,
                expires_at=case.expires_at,
                evidence=[
                    EvidenceOwnerDTO(
                        id=e.id,
                        evidence_type=e.evidence_type,
                        media_id=e.media_id,
                        submitted_by=e.submitted_by,
                        source_description=e.source_description,
                        captured_at=e.captured_at,
                        review_status=e.review_status,
                    )
                    for e in evidence_list
                ],
            )
