"""Reject verification use case."""
from __future__ import annotations

from datetime import UTC, datetime

import structlog

from camp_match.modules.verification.application.errors import (
    DecisionNotAllowed,
    InvalidVerificationTransition,
    VerificationCaseNotFound,
)
from camp_match.modules.verification.application.ports.inbound import (
    RejectVerificationRequest,
)
from camp_match.modules.verification.application.ports.outbound import (
    HistoryRepository,
    VerificationCaseRepository,
    VerificationDecisionRepository,
)
from camp_match.modules.verification.domain.entities import VerificationDecision
from camp_match.modules.verification.domain.events import VerificationDecisionRecorded
from camp_match.modules.verification.domain.value_objects import (
    DecisionOutcome,
    VerificationStatus,
)
from camp_match.shared_kernel.application.event_bus import (
    EventBus,
    NoOpEventBus,
    publish_best_effort,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class RejectVerificationUseCase:
    def __init__(
        self,
        case_repo: VerificationCaseRepository,
        decision_repo: VerificationDecisionRepository,
        history_repo: HistoryRepository,
        uow: UnitOfWork,
        event_bus: EventBus | None = None,
    ):
        self.case_repo = case_repo
        self.decision_repo = decision_repo
        self.history_repo = history_repo
        self.uow = uow
        self.event_bus = event_bus or NoOpEventBus()

    async def execute(self, request: RejectVerificationRequest) -> None:
        if not request.reason or not request.reason.strip():
            raise InvalidVerificationTransition("Rejection reason is required.")

        case = await self.case_repo.get_by_id(request.case_id)
        if not case:
            raise VerificationCaseNotFound()

        if case.status != VerificationStatus.DECISION_PENDING:
            raise InvalidVerificationTransition("Case must be in DECISION_PENDING status to reject.")

        decision_id = EntityId.new()
        decision = VerificationDecision(
            id=decision_id,
            verification_case_id=case.id,
            outcome=DecisionOutcome.REJECTED,
            reason=request.reason,
            decided_by=request.caller_id,
        )

        async with self.uow:
            updated = await self.case_repo.update_status_conditionally(
                case_id=case.id,
                expected_status=VerificationStatus.DECISION_PENDING,
                new_status=VerificationStatus.REJECTED,
            )
            if not updated:
                raise DecisionNotAllowed("Concurrency conflict: Case was already decided by another process.")

            await self.decision_repo.add(decision)
            await self.history_repo.add(
                case_id=case.id,
                event_type="verification_rejected",
                actor_id=request.caller_id,
                details=f"Verification rejected: {request.reason}",
            )
            await self.uow.commit()

        event = VerificationDecisionRecorded(
            event_id=EntityId.new(),
            occurred_at=datetime.now(UTC),
            case_id=case.id,
            target_type=case.target_type,
            target_id=case.target_id,
            decision="REJECTED",
        )
        await publish_best_effort(self.event_bus, event, logger)
