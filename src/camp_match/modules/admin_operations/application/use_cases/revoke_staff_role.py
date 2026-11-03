from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.application.errors import (
    AccountNotFound,
    InvalidReason,
    RoleNotManageable,
    SelfActionNotAllowed,
)
from camp_match.modules.admin_operations.application.ports.inbound import StaffView
from camp_match.modules.admin_operations.domain.value_objects import (
    AdminActionType,
    AuditTargetType,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class RevokeStaffRoleUseCase:
    def __init__(
        self,
        account_provider: Any,
        staff_role_provider: Any,
        authorizer: Any,
        audit_recorder: Any,
        settings: Any,
    ) -> None:
        self._account_provider = account_provider
        self._staff_role_provider = staff_role_provider
        self._authorizer = authorizer
        self._audit_recorder = audit_recorder
        self._settings = settings

    async def execute(
        self, actor_id: EntityId, identity_id: EntityId, role: str, reason: str
    ) -> StaffView:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_STAFF_MANAGE)

        min_len = getattr(self._settings, "admin_reason_min_length", 10)
        if not reason or len(reason.strip()) < min_len:
            raise InvalidReason(f"Reason must be at least {min_len} characters.")

        if role != "OPERATIONS":
            raise RoleNotManageable("Only the OPERATIONS role is manageable.")

        if actor_id == identity_id:
            raise SelfActionNotAllowed("Cannot revoke role from yourself.")

        info = await self._account_provider.get(identity_id)
        if not info:
            raise AccountNotFound(f"Account {identity_id} not found.")

        async def action() -> None:
            await self._staff_role_provider.revoke(actor_id, identity_id, role)

        await self._audit_recorder.execute(
            actor_id=actor_id,
            action_type=AdminActionType.STAFF_ROLE_REVOKE,
            target_type=AuditTargetType.IDENTITY,
            target_id=identity_id,
            reason=reason,
            details={"role": role},
            action=action,
        )

        roles = await self._staff_role_provider.get_roles(identity_id)
        return StaffView(identity_id=identity_id, roles=roles)
