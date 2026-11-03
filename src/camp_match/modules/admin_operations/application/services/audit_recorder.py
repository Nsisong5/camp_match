from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog

from camp_match.modules.admin_operations.domain.entities import AuditEvent
from camp_match.modules.admin_operations.domain.value_objects import (
    AdminActionType,
    AuditEventType,
    AuditTargetType,
)
from camp_match.shared_kernel.application.errors import ApplicationError
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class AuditRecorder:
    def __init__(self, audit_repo: Any, uow_factory: Any, clock: Any) -> None:
        self._audit_repo = audit_repo
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self,
        *,
        actor_id: EntityId,
        action_type: AdminActionType,
        target_type: AuditTargetType,
        target_id: EntityId | None = None,
        reason: str,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
        action: Callable[[], Any],
        crash_simulation: bool = False,
    ) -> tuple[Any, EntityId]:
        action_id = EntityId.new()
        now = self._clock.now()
        details_dict = details or {}

        # 1. Write ACTION_REQUESTED in its own UoW and commit first
        async with self._uow_factory() as uow:
            req_event = AuditEvent(
                id=EntityId.new(),
                action_id=action_id,
                event_type=AuditEventType.ACTION_REQUESTED,
                action_type=action_type,
                actor_id=actor_id,
                target_type=target_type,
                target_id=target_id,
                reason=reason,
                occurred_at=now,
                request_id=request_id,
                details=details_dict,
            )
            await self._audit_repo.add(req_event)
            await uow.commit()

        if crash_simulation:
            raise RuntimeError("Simulated crash after request commit.")

        # 2. Call action
        try:
            result = await action()
        except ApplicationError as app_err:
            outcome_code = getattr(app_err, "code", app_err.__class__.__name__)
            try:
                async with self._uow_factory() as uow:
                    fail_event = AuditEvent(
                        id=EntityId.new(),
                        action_id=action_id,
                        event_type=AuditEventType.ACTION_FAILED,
                        action_type=action_type,
                        actor_id=actor_id,
                        target_type=target_type,
                        target_id=target_id,
                        reason=reason,
                        outcome_code=str(outcome_code),
                        occurred_at=self._clock.now(),
                        request_id=request_id,
                        details=details_dict,
                    )
                    await self._audit_repo.add(fail_event)
                    await uow.commit()
            except Exception as write_err:
                logger.error(
                    "audit_outcome_write_failed",
                    action_id=str(action_id.value),
                    error=str(write_err),
                )
            raise app_err
        except Exception as exc:
            outcome_code = exc.__class__.__name__
            try:
                async with self._uow_factory() as uow:
                    fail_event = AuditEvent(
                        id=EntityId.new(),
                        action_id=action_id,
                        event_type=AuditEventType.ACTION_FAILED,
                        action_type=action_type,
                        actor_id=actor_id,
                        target_type=target_type,
                        target_id=target_id,
                        reason=reason,
                        outcome_code=str(outcome_code),
                        occurred_at=self._clock.now(),
                        request_id=request_id,
                        details=details_dict,
                    )
                    await self._audit_repo.add(fail_event)
                    await uow.commit()
            except Exception as write_err:
                logger.error(
                    "audit_outcome_write_failed",
                    action_id=str(action_id.value),
                    error=str(write_err),
                )
            raise exc

        # 3. Success outcome
        try:
            async with self._uow_factory() as uow:
                succ_event = AuditEvent(
                    id=EntityId.new(),
                    action_id=action_id,
                    event_type=AuditEventType.ACTION_SUCCEEDED,
                    action_type=action_type,
                    actor_id=actor_id,
                    target_type=target_type,
                    target_id=target_id,
                    reason=reason,
                    outcome_code="ok",
                    occurred_at=self._clock.now(),
                    request_id=request_id,
                    details=details_dict,
                )
                await self._audit_repo.add(succ_event)
                await uow.commit()
        except Exception as write_err:
            logger.error(
                "audit_outcome_write_failed",
                action_id=str(action_id.value),
                error=str(write_err),
            )

        return (result, action_id)
