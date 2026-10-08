from __future__ import annotations

from camp_match.modules.verification.application.errors import (
    VerificationCaseNotFound,
    InvalidVerificationTransition,
    VerificationForbiddenError,
)
from camp_match.modules.verification.application.ports.inbound import (
    AddEvidenceRequest,
    AddEvidenceResponse,
)
from camp_match.modules.verification.application.ports.outbound import (
    EvidenceRepository,
    HistoryRepository,
    InspectionRepository,
    MediaProvider,
    VerificationCaseRepository,
)
from camp_match.modules.verification.domain.entities import Evidence
from camp_match.modules.verification.domain.value_objects import VerificationStatus
from camp_match.modules.media.application.errors import MediaTooLarge, UnsupportedMediaType
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId


class AddEvidenceUseCase:
    def __init__(
        self,
        case_repo: VerificationCaseRepository,
        evidence_repo: EvidenceRepository,
        inspection_repo: InspectionRepository,
        history_repo: HistoryRepository,
        media_provider: MediaProvider,
        uow: UnitOfWork,
    ):
        self.case_repo = case_repo
        self.evidence_repo = evidence_repo
        self.inspection_repo = inspection_repo
        self.history_repo = history_repo
        self.media_provider = media_provider
        self.uow = uow

    async def execute(self, request: AddEvidenceRequest) -> AddEvidenceResponse:
        case = await self.case_repo.get_by_id(request.case_id)
        if not case:
            raise VerificationCaseNotFound()

        terminal_statuses = {
            VerificationStatus.VERIFIED,
            VerificationStatus.REJECTED,
            VerificationStatus.REVOKED,
            VerificationStatus.CANCELLED,
        }
        if case.status in terminal_statuses:
            raise InvalidVerificationTransition("Cannot add evidence to a case in a terminal state.")

        active_inspection = await self.inspection_repo.get_active_by_case_id(case.id)

        is_owner = request.caller_id == case.submitted_by
        is_assigned_inspector = (
            active_inspection is not None
            and active_inspection.inspector_id == request.caller_id
        )

        if not is_owner and not is_assigned_inspector:
            raise VerificationForbiddenError("Caller is neither case owner nor assigned inspector.")

        try:
            media_id = await self.media_provider.upload(
                purpose="VERIFICATION_EVIDENCE",
                content=request.content,
                content_type=request.content_type,
                uploaded_by=request.caller_id,
            )
        except (MediaTooLarge, UnsupportedMediaType) as e:
            raise InvalidVerificationTransition(str(e))

        evidence_id = EntityId.new()
        inspection_id = active_inspection.id if is_assigned_inspector and active_inspection else None

        evidence = Evidence(
            id=evidence_id,
            verification_case_id=case.id,
            evidence_type=request.evidence_type,
            media_id=media_id,
            submitted_by=request.caller_id,
            source_description=request.source_description,
            captured_at=request.captured_at,
            inspection_id=inspection_id,
        )

        async with self.uow:
            await self.evidence_repo.add(evidence)
            await self.history_repo.add(
                case_id=case.id,
                event_type="evidence_added",
                actor_id=request.caller_id,
                details=f"Evidence type {request.evidence_type.value} added",
            )
            await self.uow.commit()

        return AddEvidenceResponse(evidence_id=evidence_id)
