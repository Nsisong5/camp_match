"""Open case from report use case for Trust & Safety."""
from __future__ import annotations

from typing import Any

from camp_match.modules.security.domain.value_objects import Permission
from camp_match.modules.trust_safety.application.errors import ReportAlreadyLinked, ReportNotFound
from camp_match.modules.trust_safety.application.ports.outbound import (
    CaseRepository,
    DecisionRepository,
    EnforcementRepository,
    EvidenceRepository,
    NoteRepository,
    ReportRepository,
)
from camp_match.modules.trust_safety.domain.entities import SafetyCase
from camp_match.modules.trust_safety.domain.value_objects import CaseStatus, ReportStatus
from camp_match.modules.trust_safety.application.ports.inbound import OpenCaseFromReportRequest
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId


class OpenCaseFromReportUseCase:
    def __init__(
        self,
        case_repo: CaseRepository,
        report_repo: ReportRepository,
        evidence_repo: EvidenceRepository,
        note_repo: NoteRepository,
        decision_repo: DecisionRepository,
        enforcement_repo: EnforcementRepository,
        authorization_service: Any,
        unit_of_work: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._case_repo = case_repo
        self._report_repo = report_repo
        self._evidence_repo = evidence_repo
        self._note_repo = note_repo
        self._decision_repo = decision_repo
        self._enforcement_repo = enforcement_repo
        self._auth = authorization_service
        self._uow = unit_of_work
        self._clock = clock

    async def execute(self, request: OpenCaseFromReportRequest) -> EntityId:
        await self._auth.authorize(request.actor_id, Permission.SAFETY_CASE_REVIEW)

        report = await self._report_repo.get_by_id(request.report_id)
        if not report:
            raise ReportNotFound("Report not found.")

        if report.status == ReportStatus.LINKED:
            raise ReportAlreadyLinked("Report is already linked to a case.")

        now = self._clock.now()
        case_id = EntityId.new()
        case = SafetyCase(
            id=case_id,
            category=report.category,
            priority=request.priority,
            status=CaseStatus.OPEN,
            subject_user_id=report.subject_user_id,
            assigned_to=None,
            version=1,
            cycle=1,
            created_by=request.actor_id,
            created_at=now,
            updated_at=now,
        )

        async with self._uow:
            await self._case_repo.add(case)
            await self._case_repo.link_report(case_id, report.id)
            report.status = ReportStatus.LINKED
            await self._case_repo.add_event(case_id, report.id, "CASE_OPENED_FROM_REPORT", request.actor_id, {"report_id": str(report.id)})
            await self._uow.commit()

        return case_id
