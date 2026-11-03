from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.application.errors import RoleNotManageable
from camp_match.modules.admin_operations.application.ports.outbound import StaffRoleProvider
from camp_match.modules.security.application.errors import (
    RoleNotManageable as SecurityRoleNotManageable,
)
from camp_match.modules.security.domain.value_objects import Role
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessStaffRoleProvider(StaffRoleProvider):
    def __init__(
        self,
        assign_uc: Any,
        revoke_uc: Any,
        list_staff_uc: Any,
        get_roles_uc: Any,
    ) -> None:
        self._assign = assign_uc
        self._revoke = revoke_uc
        self._list = list_staff_uc
        self._get_roles = get_roles_uc

    async def assign(
        self, actor_id: EntityId, identity_id: EntityId, role: str
    ) -> None:
        try:
            await self._assign.execute(actor_id, identity_id, Role[role])
        except SecurityRoleNotManageable as e:
            raise RoleNotManageable(str(e)) from e

    async def revoke(
        self, actor_id: EntityId, identity_id: EntityId, role: str
    ) -> None:
        try:
            await self._revoke.execute(actor_id, identity_id, Role[role])
        except SecurityRoleNotManageable as e:
            raise RoleNotManageable(str(e)) from e

    async def list(
        self,
        actor_id: EntityId,
        role: str,
        page_request: PageRequest | None = None,
    ) -> Page[tuple[EntityId, frozenset[str]]]:
        req = page_request or PageRequest(page=1, page_size=20)
        id_page = await self._list.execute(actor_id, Role[role], req)
        items = [(uid, frozenset([role])) for uid in id_page.items]
        return Page(
            items=items,
            total=id_page.total,
            page=id_page.page,
            page_size=id_page.page_size,
        )

    async def get_roles(self, identity_id: EntityId) -> frozenset[str]:
        roles = await self._get_roles.execute(identity_id)
        return frozenset(r.name for r in roles)
