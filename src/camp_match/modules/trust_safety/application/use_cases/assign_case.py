"""Assign case use case for Trust & Safety."""
from __future__ import annotations

from typing import Any

from camp_match.modules.security.domain.value_objects import Permission
from camp_match.modules.trust_safety.application.errors import CaseStateChanged, ForbiddenError
from camp_match.modules.trust_safety.application.ports.inbound import AssignCaseRequest
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock


class AssignCaseUseCase:
    def __init__(
        self,
        case_repo: Any,
        case_access: CaseAccess,
        auth_service: Any,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._case_repo = case_repo
        self._case_access = case_access
        self._auth = auth_service
        self._uow = uow
        self._clock = clock

    async def execute(self, request: AssignCaseRequest) -> None:
        case = await self._case_access.require_reviewer(request.actor_id, request.case_id)
        if request.assignee_id is not None:
            try:
                await self._auth.authorize(request.assignee_id, Permission.SAFETY_CASE_REVIEW)
            except Exception as e:
                raise ForbiddenError("Assignee must hold SAFETY_CASE_REVIEW.") from e

        old_version = case.version
        case.assigned_to = request.assignee_id
        case.version += 1
        case.updated_at = self._clock.now()

        async with self._uow:
            updated = await self._case_repo.update(case, old_version)
            if not updated:
                raise CaseStateChanged("Case was modified concurrently.")
            await self._case_repo.add_event(
                case.id,
                None,
                "CASE_ASSIGNED",
                request.actor_id,
                {"assignee_id": str(request.assignee_id) if request.assignee_id else None},
            )
            await self._uow.commit()
