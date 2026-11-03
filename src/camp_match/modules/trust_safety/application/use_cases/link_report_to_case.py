"""Link report to case use case for Trust & Safety."""
from __future__ import annotations

from typing import Any

from camp_match.modules.trust_safety.application.errors import (
    ReportAlreadyLinked,
    ReportNotFound,
)
from camp_match.modules.trust_safety.application.ports.inbound import LinkReportToCaseRequest
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.modules.trust_safety.domain.value_objects import CaseStatus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock


class LinkReportToCaseUseCase:
    def __init__(
        self,
        case_repo: Any,
        report_repo: Any,
        case_access: CaseAccess,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._case_repo = case_repo
        self._report_repo = report_repo
        self._case_access = case_access
        self._uow = uow
        self._clock = clock

    async def execute(self, request: LinkReportToCaseRequest) -> None:
        case = await self._case_access.require_reviewer(request.actor_id, request.case_id)
        if case.status == CaseStatus.CLOSED:
            raise ReportAlreadyLinked("Cannot link report to a closed case.")

        report = await self._report_repo.get_by_id(request.report_id)
        if not report:
            raise ReportNotFound("Report not found.")

        linked = await self._report_repo.list_by_case_id(request.case_id)
        if any(r.id == report.id for r in linked):
            raise ReportAlreadyLinked("Report is already linked to this case.")

        async with self._uow:
            await self._case_repo.link_report(case.id, report.id)
            await self._case_repo.add_event(
                case.id,
                "REPORT_LINKED",
                request.actor_id,
                f"Report {report.id} linked.",
            )
            await self._uow.commit()
