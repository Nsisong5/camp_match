from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from camp_match.modules.admin_operations.application.errors import (
    InvalidReason,
)
from camp_match.modules.admin_operations.domain.entities import DomainError
from camp_match.modules.admin_operations.application.ports.inbound import StaffView
from camp_match.modules.admin_operations.domain.value_objects import (
    AdminActionType,
    AuditTargetType,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class ApproveStaffRoleGrantUseCase:
    def __init__(
        self,
        role_request_repo: Any,
        staff_role_provider: Any,
        authorizer: Any,
        audit_recorder: Any,
        uow: Any,
        clock: Any,
        settings: Any,
    ) -> None:
        self._role_request_repo = role_request_repo
        self._staff_role_provider = staff_role_provider
        self._authorizer = authorizer
        self._audit_recorder = audit_recorder
        self._uow = uow
        self._clock = clock
        self._settings = settings

    async def execute(
        self, actor_id: EntityId, request_id: EntityId, reason: str
    ) -> StaffView:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_STAFF_MANAGE)

        min_len = getattr(self._settings, "admin_reason_min_length", 10)
        if not reason or len(reason.strip()) < min_len:
            raise InvalidReason(f"Reason must be at least {min_len} characters.")

        now = self._clock.now()

        async with self._uow:
            req = await self._role_request_repo.get(request_id)
            if not req:
                raise DomainError("Role grant request not found.")

            if req.status != "PENDING":
                raise DomainError(f"Role grant request is already {req.status}.")

            if req.expires_at <= now:
                raise DomainError("Role grant request has expired.")

            if req.requested_by == actor_id:
                raise DomainError("Cannot approve your own role grant request.")

            if req.target_identity_id == actor_id:
                raise DomainError("Cannot approve a role grant request for yourself.")

            updated = await self._role_request_repo.update_decision(
                request_id=request_id,
                status="APPROVED",
                decided_by=actor_id,
                decided_at=now,
                decision_reason=reason,
            )
            if not updated:
                raise DomainError("Failed to approve role grant request (concurrent modification).")

            async def action() -> None:
                await self._staff_role_provider.assign(actor_id, req.target_identity_id, req.role)

            await self._audit_recorder.execute(
                actor_id=actor_id,
                action_type=AdminActionType.STAFF_ROLE_GRANT,
                target_type=AuditTargetType.IDENTITY,
                target_id=req.target_identity_id,
                reason=reason,
                details={"request_id": str(request_id), "role": req.role, "requested_by": str(req.requested_by)},
                action=action,
            )
            await self._uow.commit()

        roles = await self._staff_role_provider.get_roles(req.target_identity_id)
        return StaffView(identity_id=req.target_identity_id, roles=roles)
