from __future__ import annotations

from datetime import UTC, datetime

from camp_match.modules.verification.application.errors import (
    InspectionNotFound,
    InvalidVerificationTransition,
    VerificationCaseNotFound,
    VerificationForbiddenError,
)
from camp_match.modules.verification.application.ports.inbound import (
    CompleteInspectionRequest,
    CompleteInspectionResponse,
)
from camp_match.modules.verification.application.ports.outbound import (
    HistoryRepository,
    InspectionObservationRepository,
    InspectionRepository,
    VerificationCaseRepository,
)
from camp_match.modules.verification.domain.state_machine import transition
from camp_match.modules.verification.domain.value_objects import (
    ChecklistItem,
    InspectionResult,
    InspectionStatus,
    VerificationStatus,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork


class CompleteInspectionUseCase:
    def __init__(
        self,
        inspection_repo: InspectionRepository,
        observation_repo: InspectionObservationRepository,
        case_repo: VerificationCaseRepository,
        history_repo: HistoryRepository,
        uow: UnitOfWork,
    ):
        self.inspection_repo = inspection_repo
        self.observation_repo = observation_repo
        self.case_repo = case_repo
        self.history_repo = history_repo
        self.uow = uow

    async def execute(self, request: CompleteInspectionRequest) -> CompleteInspectionResponse:
        inspection = await self.inspection_repo.get_by_id(request.inspection_id)
        if not inspection:
            raise InspectionNotFound()

        if inspection.inspector_id != request.caller_id:
            raise VerificationForbiddenError("Only the assigned inspector may complete this inspection.")

        if inspection.status != InspectionStatus.IN_PROGRESS:
            raise InvalidVerificationTransition("Inspection must be IN_PROGRESS to complete.")

        observations = await self.observation_repo.list_by_inspection_id(inspection.id)
        recorded_items = {obs.item for obs in observations}
        required_items = set(ChecklistItem)

        missing_items = required_items - recorded_items
        if missing_items:
            missing_names = ", ".join(item.value for item in missing_items)
            raise InvalidVerificationTransition(f"Cannot complete inspection. Missing checklist items: {missing_names}")

        passed_count = sum(1 for obs in observations if obs.passed)
        total_count = len(observations)

        if passed_count == total_count:
            result = InspectionResult.PASSED
        elif passed_count == 0:
            result = InspectionResult.FAILED
        else:
            result = InspectionResult.PARTIALLY_PASSED

        inspection.status = InspectionStatus.COMPLETED
        inspection.completed_at = datetime.now(UTC)
        inspection.result = result

        case = await self.case_repo.get_by_id(inspection.verification_case_id)
        if not case:
            raise VerificationCaseNotFound()

        transition(case, VerificationStatus.INSPECTION_COMPLETED)

        async with self.uow:
            await self.inspection_repo.update(inspection)
            await self.case_repo.update(case)
            await self.history_repo.add(
                case_id=case.id,
                event_type="inspection_completed",
                actor_id=request.caller_id,
                details=f"Inspection completed with result {result.value}",
            )
            await self.uow.commit()

        return CompleteInspectionResponse(
            inspection_id=inspection.id,
            result=result,
        )
