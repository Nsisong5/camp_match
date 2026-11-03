"""Process enforcement queue use case for Trust & Safety (Chunk 13)."""
from __future__ import annotations

from typing import Any

import structlog

from camp_match.config.settings import get_settings
from camp_match.modules.trust_safety.application.errors import (
    PermanentEnforcementError,
    TransientEnforcementError,
)
from camp_match.modules.trust_safety.application.ports.events import SafetyUpdatePublished
from camp_match.modules.trust_safety.application.ports.outbound import (
    AccountEnforcer,
    CaseRepository,
    CommunicationEnforcer,
    EnforcementRepository,
    ListingEnforcer,
)
from camp_match.modules.trust_safety.domain.policies import backoff_delay_seconds
from camp_match.modules.trust_safety.domain.value_objects import EnforcementStatus, EnforcementType
from camp_match.shared_kernel.application.event_bus import EventBus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class ProcessEnforcementQueueUseCase:
    def __init__(
        self,
        enforcement_repo: EnforcementRepository,
        case_repo: CaseRepository,
        account_enforcer: AccountEnforcer,
        listing_enforcer: ListingEnforcer,
        communication_enforcer: CommunicationEnforcer,
        event_bus: EventBus,
        unit_of_work: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._enforcement_repo = enforcement_repo
        self._case_repo = case_repo
        self._account_enforcer = account_enforcer
        self._listing_enforcer = listing_enforcer
        self._communication_enforcer = communication_enforcer
        self._event_bus = event_bus
        self._uow = unit_of_work
        self._clock = clock

    async def execute(self, limit: int = 100) -> dict[str, int]:
        now = self._clock.now()
        settings = get_settings()
        due_actions = await self._enforcement_repo.list_due(now, limit)
        stats = {"applied": 0, "failed": 0, "retried": 0, "reversed": 0, "expired": 0}

        for action in due_actions:
            # Handle expired communication restrictions
            if (
                action.status == EnforcementStatus.APPLIED
                and action.action_type == EnforcementType.COMMUNICATION_RESTRICTION
                and action.ends_at is not None
                and action.ends_at <= now
            ):
                action.status = EnforcementStatus.EXPIRED
                async with self._uow:
                    await self._enforcement_repo.update(action, expected_status=EnforcementStatus.APPLIED)
                    await self._case_repo.add_event(
                        case_id=action.case_id,
                        report_id=None,
                        event_type="ENFORCEMENT_EXPIRED",
                        actor_id=None,
                        details={"action_id": str(action.id)},
                    )
                    await self._uow.commit()

                try:
                    await self._event_bus.publish(
                        SafetyUpdatePublished(report_id=action.id, update_type="RESTRICTION_LIFTED")
                    )
                except Exception:
                    pass
                stats["expired"] += 1
                continue

            if action.status == EnforcementStatus.APPROVED:
                expected_status = EnforcementStatus.APPROVED
                try:
                    if action.action_type == EnforcementType.ACCOUNT_SUSPENSION:
                        assert action.target_user_id is not None
                        await self._account_enforcer.disable(action.target_user_id)
                    elif action.action_type == EnforcementType.LISTING_SUSPENSION:
                        assert action.target_listing_id is not None
                        await self._listing_enforcer.suspend(EntityId.new(), action.target_listing_id, action.id)
                    elif action.action_type == EnforcementType.COMMUNICATION_RESTRICTION:
                        assert action.target_user_id is not None
                        assert action.ends_at is not None
                        await self._communication_enforcer.restrict(
                            EntityId.new(), action.target_user_id, action.ends_at, action.id
                        )

                    action.status = EnforcementStatus.APPLIED
                    action.applied_at = now
                    stats["applied"] += 1
                except TransientEnforcementError as e:
                    action.attempts += 1
                    action.last_error = str(e)
                    if action.attempts >= settings.safety_enforcement_max_attempts:
                        action.status = EnforcementStatus.FAILED
                        logger.error("safety_enforcement_exhausted", action_id=str(action.id), attempts=action.attempts)
                        stats["failed"] += 1
                    else:
                        action.next_attempt_at = now.fromtimestamp(
                            now.timestamp() + backoff_delay_seconds(action.attempts), tz=now.tzinfo
                        )
                        stats["retried"] += 1
                except PermanentEnforcementError as e:
                    action.status = EnforcementStatus.FAILED
                    action.last_error = str(e)
                    stats["failed"] += 1

                async with self._uow:
                    await self._enforcement_repo.update(action, expected_status=expected_status)
                    await self._case_repo.add_event(
                        case_id=action.case_id,
                        report_id=None,
                        event_type="ENFORCEMENT_APPLIED" if action.status == EnforcementStatus.APPLIED else "ENFORCEMENT_ATTEMPT_FAILED",
                        actor_id=None,
                        details={"action_id": str(action.id), "status": action.status.value},
                    )
                    await self._uow.commit()

                if action.status == EnforcementStatus.APPLIED:
                    try:
                        await self._event_bus.publish(
                            SafetyUpdatePublished(report_id=action.id, update_type=f"{action.action_type.value}_APPLIED")
                        )
                    except Exception:
                        pass

            elif action.status == EnforcementStatus.REVERSAL_PENDING:
                expected_status = EnforcementStatus.REVERSAL_PENDING
                try:
                    if action.action_type == EnforcementType.ACCOUNT_SUSPENSION:
                        assert action.target_user_id is not None
                        await self._account_enforcer.reactivate(action.target_user_id)
                    elif action.action_type == EnforcementType.LISTING_SUSPENSION:
                        assert action.target_listing_id is not None
                        await self._listing_enforcer.lift(EntityId.new(), action.target_listing_id, action.id)
                    elif action.action_type == EnforcementType.COMMUNICATION_RESTRICTION:
                        await self._communication_enforcer.lift(EntityId.new(), action.id)

                    action.status = EnforcementStatus.REVERSED
                    action.reversed_at = now
                    stats["reversed"] += 1
                except TransientEnforcementError as e:
                    action.attempts += 1
                    action.last_error = str(e)
                    if action.attempts >= settings.safety_enforcement_max_attempts:
                        action.status = EnforcementStatus.REVERSAL_FAILED
                        logger.error("safety_reversal_exhausted", action_id=str(action.id), attempts=action.attempts)
                        stats["failed"] += 1
                    else:
                        action.next_attempt_at = now.fromtimestamp(
                            now.timestamp() + backoff_delay_seconds(action.attempts), tz=now.tzinfo
                        )
                        stats["retried"] += 1
                except PermanentEnforcementError as e:
                    action.status = EnforcementStatus.REVERSAL_FAILED
                    action.last_error = str(e)
                    stats["failed"] += 1

                async with self._uow:
                    await self._enforcement_repo.update(action, expected_status=expected_status)
                    await self._case_repo.add_event(
                        case_id=action.case_id,
                        report_id=None,
                        event_type="ENFORCEMENT_REVERSED" if action.status == EnforcementStatus.REVERSED else "ENFORCEMENT_REVERSAL_FAILED",
                        actor_id=None,
                        details={"action_id": str(action.id), "status": action.status.value},
                    )
                    await self._uow.commit()

                if action.status == EnforcementStatus.REVERSED:
                    try:
                        await self._event_bus.publish(
                            SafetyUpdatePublished(report_id=action.id, update_type=f"{action.action_type.value}_REVERSED")
                        )
                    except Exception:
                        pass

        return stats
