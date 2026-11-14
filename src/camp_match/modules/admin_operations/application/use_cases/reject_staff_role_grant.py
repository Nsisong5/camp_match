from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.application.errors import (
    InvalidReason,
)
from camp_match.modules.admin_operations.domain.entities import DomainError
from camp_match.modules.admin_operations.application.ports.inbound import (
    RoleGrantRequestView,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class RejectStaffRoleGrantUseCase:
    def __init__(
        self,
        role_request_repo: Any,
        authorizer: Any,
        uow: Any,
        clock: Any,
        settings: Any,
    ) -> None:
        self._role_request_repo = role_request_repo
        self._authorizer = authorizer
        self._uow = uow
        self._clock = clock
        self._settings = settings

    async def execute(
        self, actor_id: EntityId, request_id: EntityId, reason: str
    ) -> RoleGrantRequestView:
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

            updated = await self._role_request_repo.update_decision(
                request_id=request_id,
                status="REJECTED",
                decided_by=actor_id,
                decided_at=now,
                decision_reason=reason,
            )
            if not updated:
                raise DomainError("Failed to reject role grant request.")
            await self._uow.commit()

        updated_req = await self._role_request_repo.get(request_id)
        assert updated_req is not None
        return RoleGrantRequestView(
            id=updated_req.id,
            target_identity_id=updated_req.target_identity_id,
            role=updated_req.role,
            requested_by=updated_req.requested_by,
            reason=updated_req.reason,
            status=updated_req.status,
            decided_by=updated_req.decided_by,
            decided_at=updated_req.decided_at,
            decision_reason=updated_req.decision_reason,
            created_at=updated_req.created_at,
            expires_at=updated_req.expires_at,
        )
