"""Reverse enforcement use case for Trust & Safety (Chunk 13)."""
from __future__ import annotations

from typing import Any

from camp_match.modules.trust_safety.application.errors import (
    EnforcementActionNotFound,
    InvalidEnforcementTransition,
    PermanentEnforcementError,
    TransientEnforcementError,
)
from camp_match.modules.trust_safety.application.ports.events import SafetyUpdatePublished
from camp_match.modules.trust_safety.application.ports.inbound import ReverseEnforcementRequest
from camp_match.modules.trust_safety.application.ports.outbound import (
    AccountEnforcer,
    CaseRepository,
    CommunicationEnforcer,
    EnforcementRepository,
    ListingEnforcer,
)
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.modules.trust_safety.domain.value_objects import EnforcementStatus, EnforcementType
from camp_match.shared_kernel.application.event_bus import EventBus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId


class ReverseEnforcementUseCase:
    def __init__(
        self,
        enforcement_repo: EnforcementRepository,
        case_repo: CaseRepository,
        case_access: CaseAccess,
        account_enforcer: AccountEnforcer,
        listing_enforcer: ListingEnforcer,
        communication_enforcer: CommunicationEnforcer,
        event_bus: EventBus,
        unit_of_work: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._enforcement_repo = enforcement_repo
        self._case_repo = case_repo
        self._case_access = case_access
        self._account_enforcer = account_enforcer
        self._listing_enforcer = listing_enforcer
        self._communication_enforcer = communication_enforcer
        self._event_bus = event_bus
        self._uow = unit_of_work
        self._clock = clock

    async def execute(self, request: ReverseEnforcementRequest) -> None:
        action = await self._enforcement_repo.get_by_id(request.enforcement_id)
        if not action:
            raise EnforcementActionNotFound("Enforcement action not found.")

        await self._case_access.require_approver(request.actor_id, action.case_id)

        if action.action_type == EnforcementType.WARNING:
            raise InvalidEnforcementTransition("WARNING cannot be reversed.")

        if action.status != EnforcementStatus.APPLIED:
            raise InvalidEnforcementTransition(f"Cannot reverse action in status {action.status}.")

        now = self._clock.now()
        action.status = EnforcementStatus.REVERSAL_PENDING
        action.reversed_by = request.actor_id
        action.reversal_reason = request.reason

        # Inline lift attempt
        try:
            if action.action_type == EnforcementType.ACCOUNT_SUSPENSION:
                assert action.target_user_id is not None
                await self._account_enforcer.reactivate(action.target_user_id)
            elif action.action_type == EnforcementType.LISTING_SUSPENSION:
                assert action.target_listing_id is not None
                await self._listing_enforcer.lift(request.actor_id, action.target_listing_id, action.id)
            elif action.action_type == EnforcementType.COMMUNICATION_RESTRICTION:
                await self._communication_enforcer.lift(request.actor_id, action.id)

            action.status = EnforcementStatus.REVERSED
            action.reversed_at = now
        except TransientEnforcementError as e:
            action.status = EnforcementStatus.REVERSAL_PENDING
            action.last_error = str(e)
        except PermanentEnforcementError as e:
            action.status = EnforcementStatus.REVERSAL_FAILED
            action.last_error = str(e)

        async with self._uow:
            await self._enforcement_repo.update(action, expected_status=EnforcementStatus.APPLIED)
            await self._case_repo.add_event(
                case_id=action.case_id,
                report_id=None,
                event_type="ENFORCEMENT_REVERSED" if action.status == EnforcementStatus.REVERSED else "ENFORCEMENT_REVERSAL_PENDING",
                actor_id=request.actor_id,
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
