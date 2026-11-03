"""Get case history use case for Trust & Safety."""
from __future__ import annotations

from typing import Any

from camp_match.modules.trust_safety.application.ports.inbound import (
    CaseEventView,
    GetCaseHistoryRequest,
)
from camp_match.modules.trust_safety.application.ports.outbound import CaseRepository
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.shared_kernel.domain.identifiers import EntityId


class GetCaseHistoryUseCase:
    def __init__(
        self,
        case_repo: CaseRepository,
        case_access: CaseAccess,
    ) -> None:
        self._case_repo = case_repo
        self._case_access = case_access

    async def execute(self, request: GetCaseHistoryRequest) -> list[CaseEventView]:
        await self._case_access.require_reviewer(request.actor_id, request.case_id)
        events = await self._case_repo.list_events(request.case_id)
        return [
            CaseEventView(
                id=EntityId(e.id),
                case_id=EntityId(e.case_id) if e.case_id else request.case_id,
                event_type=e.event_type,
                actor_id=EntityId(e.actor_id) if e.actor_id else None,
                occurred_at=e.occurred_at,
                details=str(e.details) if e.details else None,
            )
            for e in events
        ]
