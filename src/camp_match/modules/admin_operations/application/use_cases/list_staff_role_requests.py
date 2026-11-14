from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.application.ports.inbound import (
    RoleGrantRequestView,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class ListStaffRoleRequestsUseCase:
    def __init__(
        self,
        role_request_repo: Any,
        authorizer: Any,
    ) -> None:
        self._role_request_repo = role_request_repo
        self._authorizer = authorizer

    async def execute(
        self, actor_id: EntityId, page_request: PageRequest
    ) -> Page[RoleGrantRequestView]:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_STAFF_MANAGE)

        page = await self._role_request_repo.list(page_request)
        items = [
            RoleGrantRequestView(
                id=req.id,
                target_identity_id=req.target_identity_id,
                role=req.role,
                requested_by=req.requested_by,
                reason=req.reason,
                status=req.status,
                decided_by=req.decided_by,
                decided_at=req.decided_at,
                decision_reason=req.decision_reason,
                created_at=req.created_at,
                expires_at=req.expires_at,
            )
            for req in page.items
        ]

        return Page(
            items=items,
            total=page.total,
            page=page.page,
            page_size=page.page_size,
        )
