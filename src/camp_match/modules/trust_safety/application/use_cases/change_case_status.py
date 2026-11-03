"""Change case status use case for Trust & Safety."""
from __future__ import annotations

from typing import Any

from camp_match.modules.trust_safety.application.errors import (
    CaseStateChanged,
    TransitionRequirementNotMet,
)
from camp_match.modules.trust_safety.application.ports.events import SafetyUpdatePublished
from camp_match.modules.trust_safety.application.ports.inbound import ChangeCaseStatusRequest
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.modules.trust_safety.domain.value_objects import CaseStatus, ReportStatus, SafetyUpdateKind
from camp_match.shared_kernel.application.event_bus import EventBus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock


class ChangeCaseStatusUseCase:
    def __init__(
        self,
        case_repo: Any,
        report_repo: Any,
        decision_repo: Any,
        enforcement_repo: Any,
        case_access: CaseAccess,
        auth_service: Any,
        event_bus: EventBus,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._case_repo = case_repo
        self._report_repo = report_repo
        self._decision_repo = decision_repo
        self._enforcement_repo = enforcement_repo
        self._case_access = case_access
        self._auth = auth_service
        self._event_bus = event_bus
        self._uow = uow
        self._clock = clock

    async def execute(self, request: ChangeCaseStatusRequest) -> None:
        if request.target_status in (CaseStatus.ESCALATED, CaseStatus.CLOSED):
            case = await self._case_access.require_approver(request.actor_id, request.case_id)
        else:
            case = await self._case_access.require_reviewer(request.actor_id, request.case_id)

        if request.target_status == CaseStatus.RESOLVED:
            decisions = await self._decision_repo.list_by_case_id(case.id)
            if not any(d.decision_type.value in ("VIOLATION_ESTABLISHED", "NO_VIOLATION_ESTABLISHED", "REFERRED") for d in decisions):
                raise TransitionRequirementNotMet("Resolution requires a final decision.")

        old_version = case.version
        old_status = case.status
        now = self._clock.now()

        if old_status in (CaseStatus.RESOLVED, CaseStatus.CLOSED) and request.target_status == CaseStatus.IN_REVIEW:
            case.cycle += 1
            case.resolved_at = None
            case.closed_at = None

        case.status = request.target_status
        if request.target_status == CaseStatus.RESOLVED:
            case.resolved_at = now
        elif request.target_status == CaseStatus.CLOSED:
            case.closed_at = now

        case.version += 1
        case.updated_at = now

        async with self._uow:
            updated = await self._case_repo.update(case, old_version)
            if not updated:
                raise CaseStateChanged("Case was modified concurrently.")

            await self._case_repo.add_event(
                case.id,
                None,
                f"STATUS_CHANGED_{request.target_status.value}",
                request.actor_id,
                {"from": old_status.value, "to": request.target_status.value},
            )

            if request.target_status == CaseStatus.RESOLVED:
                reports = await self._report_repo.list_by_case_id(case.id)
                for r in reports:
                    await self._report_repo.update_status(r.id, ReportStatus.CLOSED.value)
                    try:
                        await self._event_bus.publish(
                            SafetyUpdatePublished(
                                recipient_id=r.reporter_id,
                                kind=SafetyUpdateKind.REPORT_REVIEWED,
                                reference_type="REPORT",
                                reference_id=r.id,
                            )
                        )
                    except Exception:
                        pass

            await self._uow.commit()
