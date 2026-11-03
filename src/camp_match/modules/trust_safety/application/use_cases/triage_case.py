"""Triage case use case for Trust & Safety."""
from __future__ import annotations

from typing import Any

from camp_match.modules.trust_safety.application.errors import CaseStateChanged
from camp_match.modules.trust_safety.application.ports.inbound import TriageCaseRequest
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.modules.trust_safety.domain.value_objects import CasePriority
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock


class TriageCaseUseCase:
    def __init__(
        self,
        case_repo: Any,
        case_access: CaseAccess,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._case_repo = case_repo
        self._case_access = case_access
        self._uow = uow
        self._clock = clock

    async def execute(self, request: TriageCaseRequest) -> None:
        case = await self._case_access.require_reviewer(request.actor_id, request.case_id)
        old_version = case.version
        case.priority = request.priority
        case.version += 1
        case.updated_at = self._clock.now()

        async with self._uow:
            updated = await self._case_repo.update(case, old_version)
            if not updated:
                raise CaseStateChanged("Case was modified concurrently.")
            await self._case_repo.add_event(
                case.id,
                None,
                "CASE_TRIAGED",
                request.actor_id,
                {"priority": request.priority.value},
            )
            await self._uow.commit()
