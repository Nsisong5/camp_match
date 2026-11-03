from __future__ import annotations

from camp_match.modules.verification.application.errors import (
    InspectionNotFound,
    InvalidVerificationTransition,
    VerificationForbiddenError,
)
from camp_match.modules.verification.application.ports.inbound import (
    RecordInspectionObservationRequest,
    RecordInspectionObservationResponse,
)
from camp_match.modules.verification.application.ports.outbound import (
    HistoryRepository,
    InspectionObservationRepository,
    InspectionRepository,
)
from camp_match.modules.verification.domain.entities import InspectionObservation
from camp_match.modules.verification.domain.value_objects import InspectionStatus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId


class RecordInspectionObservationUseCase:
    def __init__(
        self,
        inspection_repo: InspectionRepository,
        observation_repo: InspectionObservationRepository,
        history_repo: HistoryRepository,
        uow: UnitOfWork,
    ):
        self.inspection_repo = inspection_repo
        self.observation_repo = observation_repo
        self.history_repo = history_repo
        self.uow = uow

    async def execute(
        self, request: RecordInspectionObservationRequest
    ) -> RecordInspectionObservationResponse:
        inspection = await self.inspection_repo.get_by_id(request.inspection_id)
        if not inspection:
            raise InspectionNotFound()

        if inspection.inspector_id != request.caller_id:
            raise VerificationForbiddenError("Only the assigned inspector may record observations.")

        if inspection.status != InspectionStatus.IN_PROGRESS:
            raise InvalidVerificationTransition("Inspection must be IN_PROGRESS to record observations.")

        existing = await self.observation_repo.list_by_inspection_id(inspection.id)
        if any(obs.item == request.item for obs in existing):
            raise InvalidVerificationTransition(f"Observation for checklist item {request.item.value} has already been recorded.")

        observation_id = EntityId.new()
        observation = InspectionObservation(
            id=observation_id,
            inspection_id=inspection.id,
            item=request.item,
            passed=request.passed,
            notes=request.notes,
        )

        async with self.uow:
            await self.observation_repo.add(observation)
            await self.history_repo.add(
                case_id=inspection.verification_case_id,
                event_type="inspection_observation_recorded",
                actor_id=request.caller_id,
                details=f"Observation for {request.item.value} recorded: {'passed' if request.passed else 'failed'}",
            )
            await self.uow.commit()

        return RecordInspectionObservationResponse(observation_id=observation_id)
