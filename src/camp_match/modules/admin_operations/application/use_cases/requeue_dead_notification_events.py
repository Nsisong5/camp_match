from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.application.errors import InvalidReason
from camp_match.modules.admin_operations.application.ports.inbound import (
    RecoveryResult,
)
from camp_match.modules.admin_operations.domain.value_objects import (
    AdminActionType,
    AuditTargetType,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class RequeueDeadNotificationEventsUseCase:
    def __init__(
        self,
        notification_recovery: Any,
        authorizer: Any,
        audit_recorder: Any,
        settings: Any,
    ) -> None:
        self._notification_recovery = notification_recovery
        self._authorizer = authorizer
        self._audit_recorder = audit_recorder
        self._settings = settings

    async def execute(self, actor_id: EntityId, reason: str) -> RecoveryResult:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_RECOVERY_RUN)

        min_len = getattr(self._settings, "admin_reason_min_length", 10)
        if not reason or len(reason.strip()) < min_len:
            raise InvalidReason(f"Reason must be at least {min_len} characters.")

        async def action() -> int:
            res = await self._notification_recovery.requeue_dead(actor_id)
            return int(res) if isinstance(res, (int, float)) else 0

        count, action_id = await self._audit_recorder.execute(
            actor_id=actor_id,
            action_type=AdminActionType.RECOVERY_NOTIFICATION_EVENTS,
            target_type=AuditTargetType.NONE,
            reason=reason,
            details={"requeued": 0},
            action=action,
        )
        return RecoveryResult(action_id=action_id, requeued=int(count))
