"""Approve enforcement use case for Trust & Safety (Chunk 13)."""
from __future__ import annotations

from typing import Any

from camp_match.config.settings import get_settings
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.modules.trust_safety.application.errors import (
    EnforcementActionNotFound,
    InvalidEnforcementTransition,
    PermanentEnforcementError,
    SeparationOfDutiesViolation,
    TransientEnforcementError,
)
from camp_match.modules.trust_safety.application.ports.events import SafetyUpdatePublished
from camp_match.modules.trust_safety.application.ports.inbound import ApproveEnforcementRequest
from camp_match.modules.trust_safety.application.ports.outbound import (
    AccountEnforcer,
    CaseRepository,
    CommunicationEnforcer,
    EnforcementRepository,
    ListingEnforcer,
)
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.modules.trust_safety.domain.policies import backoff_delay_seconds
from camp_match.modules.trust_safety.domain.value_objects import EnforcementStatus, EnforcementType
from camp_match.shared_kernel.application.event_bus import EventBus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId


class ApproveEnforcementUseCase:
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

    async def execute(self, request: ApproveEnforcementRequest) -> None:
        action = await self._enforcement_repo.get_by_id(request.enforcement_id)
        if not action:
            raise EnforcementActionNotFound("Enforcement action not found.")

        # Require approver role & conflict-of-interest check
        case = await self._case_access.require_approver(request.actor_id, action.case_id)

        # Separation of duties: approver cannot be proposer
        if action.proposed_by == request.actor_id:
            raise SeparationOfDutiesViolation("Approver cannot be the proposer of the action.")

        if action.status != EnforcementStatus.PROPOSED:
            raise InvalidEnforcementTransition(f"Cannot approve action in status {action.status}.")

        now = self._clock.now()
        action.status = EnforcementStatus.APPROVED
        action.approved_by = request.actor_id
        action.approved_at = now

        # Inline apply attempt
        settings = get_settings()
        try:
            if action.action_type == EnforcementType.ACCOUNT_SUSPENSION:
                assert action.target_user_id is not None
                await self._account_enforcer.disable(action.target_user_id)
            elif action.action_type == EnforcementType.LISTING_SUSPENSION:
                assert action.target_listing_id is not None
                await self._listing_enforcer.suspend(request.actor_id, action.target_listing_id, action.id)
            elif action.action_type == EnforcementType.COMMUNICATION_RESTRICTION:
                assert action.target_user_id is not None
                assert action.ends_at is not None
                await self._communication_enforcer.restrict(
                    request.actor_id, action.target_user_id, action.ends_at, action.id
                )

            action.status = EnforcementStatus.APPLIED
            action.applied_at = now
        except TransientEnforcementError as e:
            action.status = EnforcementStatus.APPROVED
            action.attempts += 1
            action.last_error = str(e)
            action.next_attempt_at = now.fromtimestamp(
                now.timestamp() + backoff_delay_seconds(action.attempts), tz=now.tzinfo
            )
        except PermanentEnforcementError as e:
            action.status = EnforcementStatus.FAILED
            action.last_error = str(e)

        async with self._uow:
            await self._enforcement_repo.update(action, expected_status=EnforcementStatus.PROPOSED)
            await self._case_repo.add_event(
                case_id=action.case_id,
                report_id=None,
                event_type="ENFORCEMENT_APPROVED" if action.status != EnforcementStatus.APPLIED else "ENFORCEMENT_APPLIED",
                actor_id=request.actor_id,
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
