"""Requeue failed enforcement use case for Trust & Safety (Chunk 13)."""
from __future__ import annotations

from typing import Any

from camp_match.modules.trust_safety.application.errors import (
    EnforcementActionNotFound,
    InvalidEnforcementTransition,
)
from camp_match.modules.trust_safety.application.ports.outbound import CaseRepository, EnforcementRepository
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.modules.trust_safety.domain.value_objects import EnforcementStatus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId


class RequeueFailedEnforcementUseCase:
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

    async def execute(self, actor_id: EntityId, action_id: EntityId) -> None:
        action = await self._enforcement_repo.get_by_id(action_id)
        if not action:
            raise EnforcementActionNotFound("Enforcement action not found.")

        await self._case_access.require_approver(actor_id, action.case_id)

        old_status = action.status
        if old_status == EnforcementStatus.FAILED:
            action.status = EnforcementStatus.APPROVED
        elif old_status == EnforcementStatus.REVERSAL_FAILED:
            action.status = EnforcementStatus.REVERSAL_PENDING
        else:
            raise InvalidEnforcementTransition(f"Cannot requeue action in status {old_status}.")

        action.attempts = 0
        action.next_attempt_at = None
        action.last_error = None

        async with self._uow:
            await self._enforcement_repo.update(action, expected_status=old_status)
            await self._case_repo.add_event(
                case_id=action.case_id,
                report_id=None,
                event_type="ENFORCEMENT_REQUEUED",
                actor_id=actor_id,
                details={"action_id": str(action.id), "from_status": old_status.value, "to_status": action.status.value},
            )
            await self._uow.commit()
