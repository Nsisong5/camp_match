from __future__ import annotations

from datetime import datetime, timedelta, timezone

from camp_match.modules.verification.application.errors import (
    VerificationCaseNotFound,
    VerificationForbiddenError,
    EvidenceRequirementNotSatisfied,
    DecisionNotAllowed,
    InvalidVerificationTransition,
)
from camp_match.modules.verification.application.ports.inbound import (
    ApproveVerificationRequest,
    ApproveVerificationResponse,
)
from camp_match.modules.verification.application.ports.outbound import (
    EvidenceRepository,
    HistoryRepository,
    InspectionRepository,
    VerificationCaseRepository,
    VerificationDecisionRepository,
)
from camp_match.modules.verification.domain.entities import VerificationDecision
from camp_match.modules.verification.domain.requirements import decision_prerequisites_satisfied
from camp_match.modules.verification.domain.value_objects import (
    DecisionOutcome,
    VerificationStatus,
    VerificationTargetType,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId


class ApproveVerificationUseCase:
    def __init__(
        self,
        case_repo: VerificationCaseRepository,
        evidence_repo: EvidenceRepository,
        inspection_repo: InspectionRepository,
        decision_repo: VerificationDecisionRepository,
        history_repo: HistoryRepository,
        uow: UnitOfWork,
    ):
        self.case_repo = case_repo
        self.evidence_repo = evidence_repo
        self.inspection_repo = inspection_repo
        self.decision_repo = decision_repo
        self.history_repo = history_repo
        self.uow = uow

    async def execute(self, request: ApproveVerificationRequest) -> ApproveVerificationResponse:
        if not request.reason or not request.reason.strip():
            raise InvalidVerificationTransition("Approval reason is required.")

        case = await self.case_repo.get_by_id(request.case_id)
        if not case:
            raise VerificationCaseNotFound()

        if case.status != VerificationStatus.DECISION_PENDING:
            raise InvalidVerificationTransition("Case must be in DECISION_PENDING status to approve.")

        inspection = await self.inspection_repo.get_latest_by_case_id(case.id)
        if inspection and inspection.inspector_id == request.caller_id:
            raise VerificationForbiddenError(
                "ADR-074 Violation: The assigned inspector cannot approve their own inspection."
            )

        evidence_list = await self.evidence_repo.list_by_case_id(case.id)
        satisfied, reason = decision_prerequisites_satisfied(case, evidence_list, inspection)
        if not satisfied:
            raise EvidenceRequirementNotSatisfied(reason or "Evidence prerequisites not satisfied.")

        days = 365 if case.target_type == VerificationTargetType.PROPERTY else 730
        expires_at = datetime.now(timezone.utc) + timedelta(days=days)

        decision_id = EntityId.new()
        decision = VerificationDecision(
            id=decision_id,
            verification_case_id=case.id,
            outcome=DecisionOutcome.VERIFIED,
            reason=request.reason,
            decided_by=request.caller_id,
        )

        async with self.uow:
            updated = await self.case_repo.update_status_conditionally(
                case_id=case.id,
                expected_status=VerificationStatus.DECISION_PENDING,
                new_status=VerificationStatus.VERIFIED,
                expires_at=expires_at,
            )
            if not updated:
                raise DecisionNotAllowed("Concurrency conflict: Case was already decided by another process.")

            await self.decision_repo.add(decision)
            await self.history_repo.add(
                case_id=case.id,
                event_type="verification_approved",
                actor_id=request.caller_id,
                details=f"Verification approved: {request.reason}",
            )

        return ApproveVerificationResponse(case_id=case.id, expires_at=expires_at)
