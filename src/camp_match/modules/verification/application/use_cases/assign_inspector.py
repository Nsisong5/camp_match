from __future__ import annotations

from camp_match.modules.verification.application.errors import (
    InvalidVerificationTransition,
    VerificationCaseNotFound,
)
from camp_match.modules.verification.application.ports.inbound import (
    AssignInspectorRequest,
    AssignInspectorResponse,
)
from camp_match.modules.verification.application.ports.outbound import (
    HistoryRepository,
    InspectionRepository,
    VerificationCaseRepository,
)
from camp_match.modules.verification.domain.entities import Inspection
from camp_match.modules.verification.domain.state_machine import transition
from camp_match.modules.verification.domain.value_objects import (
    InspectionStatus,
    VerificationStatus,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId


class AssignInspectorUseCase:
    def __init__(
        self,
        case_repo: VerificationCaseRepository,
        inspection_repo: InspectionRepository,
        history_repo: HistoryRepository,
        uow: UnitOfWork,
    ):
        self.case_repo = case_repo
        self.inspection_repo = inspection_repo
        self.history_repo = history_repo
        self.uow = uow

    async def execute(self, request: AssignInspectorRequest) -> AssignInspectorResponse:
        case = await self.case_repo.get_by_id(request.case_id)
        if not case:
            raise VerificationCaseNotFound()

        if case.status != VerificationStatus.INSPECTION_REQUIRED:
            raise InvalidVerificationTransition("Case must be in INSPECTION_REQUIRED status to assign an inspector.")

        inspection_id = EntityId.new()
        inspection = Inspection(
            id=inspection_id,
            verification_case_id=case.id,
            inspector_id=request.inspector_id,
            assigned_by=request.caller_id,
            status=InspectionStatus.ASSIGNED,
        )

        transition(case, VerificationStatus.INSPECTION_IN_PROGRESS)

        async with self.uow:
            await self.inspection_repo.add(inspection)
            await self.case_repo.update(case)
            await self.history_repo.add(
                case_id=case.id,
                event_type="inspector_assigned",
                actor_id=request.caller_id,
                details="Inspector assigned to case",
            )
            await self.uow.commit()

        return AssignInspectorResponse(inspection_id=inspection_id)
