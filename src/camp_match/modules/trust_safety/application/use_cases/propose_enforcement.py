"""Propose enforcement use case for Trust & Safety (Chunk 13)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from camp_match.config.settings import get_settings
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.modules.trust_safety.application.errors import (
    DuplicateEnforcementAction,
    InvalidDecision,
    InvalidEnforcementRequest,
    SeparationOfDutiesViolation,
)
from camp_match.modules.trust_safety.application.ports.events import SafetyUpdatePublished
from camp_match.modules.trust_safety.application.ports.inbound import ProposeEnforcementRequest
from camp_match.modules.trust_safety.application.ports.outbound import (
    CaseRepository,
    DecisionRepository,
    EnforcementRepository,
    ReportRepository,
)
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.modules.trust_safety.domain.entities import EnforcementAction
from camp_match.modules.trust_safety.domain.value_objects import (
    DecisionType,
    EnforcementStatus,
    EnforcementType,
    SubjectType,
)
from camp_match.shared_kernel.application.event_bus import EventBus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId


class ProposeEnforcementUseCase:
    def __init__(
        self,
        case_repo: CaseRepository,
        decision_repo: DecisionRepository,
        enforcement_repo: EnforcementRepository,
        report_repo: ReportRepository,
        case_access: CaseAccess,
        event_bus: EventBus,
        unit_of_work: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._case_repo = case_repo
        self._decision_repo = decision_repo
        self._enforcement_repo = enforcement_repo
        self._report_repo = report_repo
        self._case_access = case_access
        self._event_bus = event_bus
        self._uow = unit_of_work
        self._clock = clock

    async def execute(self, request: ProposeEnforcementRequest) -> EntityId:
        case = await self._case_access.require_reviewer(request.actor_id, request.case_id)

        # Precondition 1: Decision must exist, belong to this case, and be a final VIOLATION_ESTABLISHED decision
        decisions = await self._decision_repo.list_by_case_id(request.case_id)
        decision = next((d for d in decisions if d.id == request.decision_id), None)
        if not decision or decision.decision_type != DecisionType.VIOLATION_ESTABLISHED:
            raise InvalidDecision("Enforcement requires a final VIOLATION_ESTABLISHED decision.")

        # Precondition 2: Target matching
        target_key = ""
        if request.action_type == EnforcementType.LISTING_SUSPENSION:
            if not request.target_listing_id or request.target_user_id is not None:
                raise InvalidEnforcementRequest("LISTING_SUSPENSION requires target_listing_id and no target_user_id.")
            target_key = f"listing:{request.target_listing_id}"
        else:
            if not request.target_user_id or request.target_listing_id is not None:
                raise InvalidEnforcementRequest("User-targeted enforcement requires target_user_id and no target_listing_id.")
            if request.target_user_id != case.subject_user_id:
                raise InvalidEnforcementRequest("Target user must be the subject of the case.")
            target_key = f"user:{request.target_user_id}"

        # Precondition 3: Expiration bounds
        settings = get_settings()
        now = self._clock.now()
        if request.action_type == EnforcementType.COMMUNICATION_RESTRICTION:
            if not request.ends_at or request.ends_at <= now:
                raise InvalidEnforcementRequest("COMMUNICATION_RESTRICTION requires a future ends_at.")
            max_seconds = settings.safety_restriction_max_days * 86400
            if (request.ends_at - now).total_seconds() > max_seconds:
                raise InvalidEnforcementRequest("COMMUNICATION_RESTRICTION exceeds maximum duration.")
        else:
            if request.ends_at is not None:
                raise InvalidEnforcementRequest("Only COMMUNICATION_RESTRICTION can have an ends_at.")

        # Precondition 4: Duplicate live enforcement
        existing_actions = await self._enforcement_repo.list_by_case_id(request.case_id)
        live_statuses = {
            EnforcementStatus.PROPOSED,
            EnforcementStatus.APPROVED,
            EnforcementStatus.APPLIED,
            EnforcementStatus.REVERSAL_PENDING,
        }
        for a in existing_actions:
            if a.target_key == target_key and a.action_type == request.action_type and a.status in live_statuses:
                raise DuplicateEnforcementAction("Duplicate live enforcement action for target.")

        action_id = EntityId.new()
        is_warning = request.action_type == EnforcementType.WARNING
        initial_status = EnforcementStatus.APPLIED if is_warning else EnforcementStatus.PROPOSED
        applied_at = now if is_warning else None

        action = EnforcementAction(
            id=action_id,
            case_id=request.case_id,
            decision_id=request.decision_id,
            action_type=request.action_type,
            target_user_id=request.target_user_id,
            target_listing_id=request.target_listing_id,
            target_key=target_key,
            ends_at=request.ends_at,
            status=initial_status,
            rationale=request.rationale,
            proposed_by=request.actor_id,
            proposed_at=now,
            approved_by=request.actor_id if is_warning else None,
            approved_at=now if is_warning else None,
            applied_at=applied_at,
        )

        async with self._uow:
            await self._enforcement_repo.add(action)
            await self._case_repo.add_event(
                case_id=request.case_id,
                report_id=None,
                event_type="ENFORCEMENT_PROPOSED" if not is_warning else "WARNING_ISSUED",
                actor_id=request.actor_id,
                details={"action_id": str(action_id), "action_type": request.action_type.value},
            )
            await self._uow.commit()

        if is_warning:
            try:
                await self._event_bus.publish(
                    SafetyUpdatePublished(report_id=action_id, update_type="WARNING_ISSUED")
                )
            except Exception:
                pass

        return action_id
