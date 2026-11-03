from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.application.ports.inbound import StaffView
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class ListStaffUseCase:
    def __init__(self, staff_role_provider: Any, authorizer: Any) -> None:
        self._staff_role_provider = staff_role_provider
        self._authorizer = authorizer

    async def execute(
        self,
        actor_id: EntityId,
        role: str,
        page_request: PageRequest | None = None,
    ) -> Page[StaffView]:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_STAFF_MANAGE)
        req = page_request or PageRequest(page=1, page_size=20)
        page = await self._staff_role_provider.list(actor_id, role, req)
        items = [
            StaffView(identity_id=uid, roles=roles)
            for uid, roles in page.items
        ]
        return Page(
            items=items,
            total=page.total,
            page=page.page,
            page_size=page.page_size,
        )
