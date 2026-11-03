from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.application.errors import (
    AccountNotFound,
    AdminAccountProtected,
    InvalidReason,
    SelfActionNotAllowed,
)
from camp_match.modules.admin_operations.application.ports.inbound import AccountView
from camp_match.modules.admin_operations.domain.value_objects import (
    AdminActionType,
    AuditTargetType,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class DisableAccountUseCase:
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
        self, actor_id: EntityId, identity_id: EntityId, reason: str
    ) -> AccountView:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_USERS_MANAGE)

        min_len = getattr(self._settings, "admin_reason_min_length", 10)
        if not reason or len(reason.strip()) < min_len:
            raise InvalidReason(f"Reason must be at least {min_len} characters.")

        if actor_id == identity_id:
            raise SelfActionNotAllowed("Cannot disable your own account.")

        info = await self._account_provider.get(identity_id)
        if not info:
            raise AccountNotFound(f"Account {identity_id} not found.")

        roles = await self._staff_role_provider.get_roles(identity_id)
        if "ADMIN" in roles:
            raise AdminAccountProtected("Cannot disable an administrator account.")

        app_env = getattr(self._settings, "app_env", "local")
        debug_mode = getattr(self._settings, "admin_debug_account_action_mode", "")
        crash_sim = False

        if app_env in {"local", "test"}:
            if debug_mode == "downstream_fails":
                raise AccountNotFound("Simulated downstream failure")
            elif debug_mode == "crash_after_request":
                crash_sim = True

        async def action() -> None:
            await self._account_provider.disable(identity_id, reason)

        await self._audit_recorder.execute(
            actor_id=actor_id,
            action_type=AdminActionType.ACCOUNT_DISABLE,
            target_type=AuditTargetType.IDENTITY,
            target_id=identity_id,
            reason=reason,
            action=action,
            crash_simulation=crash_sim,
        )

        updated_info = await self._account_provider.get(identity_id)
        current_status = updated_info.status if updated_info else "DISABLED"
        return AccountView(
            identity_id=identity_id,
            status=current_status,
            created_at=info.created_at,
            roles=roles,
        )
