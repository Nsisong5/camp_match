from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from camp_match.modules.admin_operations.application.errors import (
    AccountNotActive,
    AccountNotFound,
    InvalidReason,
    RoleNotManageable,
    SelfActionNotAllowed,
)
from camp_match.modules.admin_operations.application.ports.inbound import (
    RoleGrantRequestView,
    StaffView,
)
from camp_match.modules.admin_operations.domain.entities import RoleGrantRequest
from camp_match.modules.admin_operations.domain.value_objects import (
    AdminActionType,
    AuditTargetType,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class GrantStaffRoleUseCase:
    def __init__(
        self,
        account_provider: Any,
        staff_role_provider: Any,
        role_request_repo: Any,
        authorizer: Any,
        audit_recorder: Any,
        uow: Any,
        clock: Any,
        settings: Any,
    ) -> None:
        self._account_provider = account_provider
        self._staff_role_provider = staff_role_provider
        self._role_request_repo = role_request_repo
        self._authorizer = authorizer
        self._audit_recorder = audit_recorder
        self._uow = uow
        self._clock = clock
        self._settings = settings

    async def execute(
        self, actor_id: EntityId, identity_id: EntityId, role: str, reason: str
    ) -> StaffView | RoleGrantRequestView:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_STAFF_MANAGE)

        min_len = getattr(self._settings, "admin_reason_min_length", 10)
        if not reason or len(reason.strip()) < min_len:
            raise InvalidReason(f"Reason must be at least {min_len} characters.")

        if role != "OPERATIONS":
            raise RoleNotManageable("Only the OPERATIONS role is manageable.")

        if actor_id == identity_id:
            raise SelfActionNotAllowed("Cannot grant role to yourself.")

        info = await self._account_provider.get(identity_id)
        if not info:
            raise AccountNotFound(f"Account {identity_id} not found.")

        if info.status != "ACTIVE":
            raise AccountNotActive(f"Account {identity_id} is not active.")

        requires_second = getattr(
            self._settings, "admin_role_grant_requires_second_approver", False
        )
        now = self._clock.now()

        if requires_second:
            async with self._uow:
                existing = await self._role_request_repo.get_pending_duplicate(
                    identity_id, role
                )
                if existing:
                    return RoleGrantRequestView(
                        id=existing.id,
                        target_identity_id=existing.target_identity_id,
                        role=existing.role,
                        requested_by=existing.requested_by,
                        reason=existing.reason,
                        status=existing.status,
                        decided_by=existing.decided_by,
                        decided_at=existing.decided_at,
                        decision_reason=existing.decision_reason,
                        created_at=existing.created_at,
                        expires_at=existing.expires_at,
                    )

                ttl = getattr(
                    self._settings, "admin_role_grant_request_ttl_seconds", 86400
                )
                expires_at = now + timedelta(seconds=ttl)
                req_id = EntityId.new()
                req = RoleGrantRequest(
                    id=req_id,
                    target_identity_id=identity_id,
                    role=role,
                    requested_by=actor_id,
                    reason=reason,
                    status="PENDING",
                    created_at=now,
                    expires_at=expires_at,
                )
                await self._role_request_repo.add(req)

                async def action() -> None:
                    pass

                await self._audit_recorder.execute(
                    actor_id=actor_id,
                    action_type=AdminActionType.STAFF_ROLE_GRANT,
                    target_type=AuditTargetType.IDENTITY,
                    target_id=identity_id,
                    reason=reason,
                    details={"request_id": str(req_id), "role": role, "status": "PENDING"},
                    action=action,
                )
                await self._uow.commit()

            return RoleGrantRequestView(
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

        else:
            async with self._uow:
                async def action() -> None:
                    await self._staff_role_provider.assign(actor_id, identity_id, role)

                await self._audit_recorder.execute(
                    actor_id=actor_id,
                    action_type=AdminActionType.STAFF_ROLE_GRANT,
                    target_type=AuditTargetType.IDENTITY,
                    target_id=identity_id,
                    reason=reason,
                    details={"role": role},
                    action=action,
                )
                await self._uow.commit()

            roles = await self._staff_role_provider.get_roles(identity_id)
            return StaffView(identity_id=identity_id, roles=roles)
