"""Reject enforcement use case for Trust & Safety (Chunk 13)."""
from __future__ import annotations

from typing import Any

from camp_match.modules.trust_safety.application.errors import (
    EnforcementActionNotFound,
    InvalidEnforcementTransition,
    SeparationOfDutiesViolation,
)
from camp_match.modules.trust_safety.application.ports.inbound import RejectEnforcementRequest
from camp_match.modules.trust_safety.application.ports.outbound import CaseRepository, EnforcementRepository
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.modules.trust_safety.domain.value_objects import EnforcementStatus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId


class RejectEnforcementUseCase:
    def __init__(
        self,
        enforcement_repo: EnforcementRepository,
        case_repo: CaseRepository,
        case_access: CaseAccess,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._enforcement_repo = enforcement_repo
        self._case_repo = case_repo
        self._case_access = case_access
        self._uow = unit_of_work

    async def execute(self, request: RejectEnforcementRequest) -> None:
        action = await self._enforcement_repo.get_by_id(request.enforcement_id)
        if not action:
            raise EnforcementActionNotFound("Enforcement action not found.")

        await self._case_access.require_approver(request.actor_id, action.case_id)

        if action.proposed_by == request.actor_id:
            raise SeparationOfDutiesViolation("Approver cannot be the proposer of the action.")

        if action.status != EnforcementStatus.PROPOSED:
            raise InvalidEnforcementTransition(f"Cannot reject action in status {action.status}.")

        action.status = EnforcementStatus.REJECTED
        action.rejected_reason = request.reason

        async with self._uow:
            await self._enforcement_repo.update(action, expected_status=EnforcementStatus.PROPOSED)
            await self._case_repo.add_event(
                case_id=action.case_id,
                report_id=None,
                event_type="ENFORCEMENT_REJECTED",
                actor_id=request.actor_id,
                details={"action_id": str(action.id), "reason": request.reason},
            )
            await self._uow.commit()
