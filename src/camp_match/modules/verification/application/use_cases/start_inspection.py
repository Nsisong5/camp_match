from __future__ import annotations

from datetime import datetime, timezone

from camp_match.modules.verification.application.errors import (
    InspectionNotFound,
    VerificationForbiddenError,
    InvalidVerificationTransition,
)
from camp_match.modules.verification.application.ports.inbound import (
    StartInspectionRequest,
    StartInspectionResponse,
)
from camp_match.modules.verification.application.ports.outbound import (
    HistoryRepository,
    InspectionRepository,
)
from camp_match.modules.verification.domain.value_objects import InspectionStatus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork


class StartInspectionUseCase:
    def __init__(
        self,
        inspection_repo: InspectionRepository,
        history_repo: HistoryRepository,
        uow: UnitOfWork,
    ):
        self.inspection_repo = inspection_repo
        self.history_repo = history_repo
        self.uow = uow

    async def execute(self, request: StartInspectionRequest) -> StartInspectionResponse:
        inspection = await self.inspection_repo.get_by_id(request.inspection_id)
        if not inspection:
            raise InspectionNotFound()

        if inspection.inspector_id != request.caller_id:
            raise VerificationForbiddenError("Only the assigned inspector may start this inspection.")

        if inspection.status != InspectionStatus.ASSIGNED:
            raise InvalidVerificationTransition("Inspection must be in ASSIGNED status to start.")

        inspection.status = InspectionStatus.IN_PROGRESS
        inspection.started_at = datetime.now(timezone.utc)

        async with self.uow:
            await self.inspection_repo.update(inspection)
            await self.history_repo.add(
                case_id=inspection.verification_case_id,
                event_type="inspection_started",
                actor_id=request.caller_id,
                details=f"Inspection {inspection.id} started",
            )
            await self.uow.commit()

        return StartInspectionResponse(inspection_id=inspection.id)
