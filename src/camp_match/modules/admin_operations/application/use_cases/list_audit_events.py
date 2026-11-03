from __future__ import annotations

from datetime import datetime
from typing import Any

from camp_match.modules.admin_operations.application.ports.inbound import (
    AuditEventView,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class ListAuditEventsUseCase:
    def __init__(self, audit_repo: Any, authorizer: Any) -> None:
        self._audit_repo = audit_repo
        self._authorizer = authorizer

    async def execute(
        self,
        actor_id: EntityId,
        actor_filter_id: EntityId | None = None,
        action_type: Any | None = None,
        target_id: EntityId | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[AuditEventView]:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_AUDIT_VIEW)
        req = page_request or PageRequest(page=1, page_size=20)
        page = await self._audit_repo.list(
            actor_id=actor_filter_id,
            action_type=action_type,
            target_id=target_id,
            from_date=from_date,
            to_date=to_date,
            page_request=req,
        )
        items = [
            AuditEventView(
                id=e.id,
                action_id=e.action_id,
                event_type=e.event_type,
                action_type=e.action_type,
                actor_id=e.actor_id,
                target_type=e.target_type,
                target_id=e.target_id,
                reason=e.reason,
                outcome_code=e.outcome_code,
                occurred_at=e.occurred_at,
                request_id=e.request_id,
                details=e.details,
            )
            for e in page.items
        ]
        return Page(
            items=items,
            total=page.total,
            page=page.page,
            page_size=page.page_size,
        )
