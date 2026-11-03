from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.application.errors import AccountNotFound
from camp_match.modules.admin_operations.application.ports.inbound import AccountView
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class GetAccountUseCase:
    def __init__(
        self,
        account_provider: Any,
        staff_role_provider: Any,
        authorizer: Any,
    ) -> None:
        self._account_provider = account_provider
        self._staff_role_provider = staff_role_provider
        self._authorizer = authorizer

    async def execute(self, actor_id: EntityId, identity_id: EntityId) -> AccountView:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_USERS_MANAGE)
        info = await self._account_provider.get(identity_id)
        if not info:
            raise AccountNotFound(f"Account {identity_id} not found.")
        roles = await self._staff_role_provider.get_roles(identity_id)
        return AccountView(
            identity_id=info.identity_id,
            status=info.status,
            created_at=info.created_at,
            roles=roles,
        )
