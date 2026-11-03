"""Get my report use case for Trust & Safety."""
from __future__ import annotations

from camp_match.modules.trust_safety.application.errors import ReportNotFound
from camp_match.modules.trust_safety.application.ports.inbound import (
    GetMyReportRequest,
    ReporterReportView,
)
from camp_match.modules.trust_safety.application.ports.outbound import ReportRepository


class GetMyReportUseCase:
    def __init__(self, report_repo: ReportRepository) -> None:
        self._report_repo = report_repo

    async def execute(self, request: GetMyReportRequest) -> ReporterReportView:
        report = await self._report_repo.get_by_id(request.report_id)
        if not report or report.reporter_id != request.actor_id:
            raise ReportNotFound("Report not found.")
        return ReporterReportView(
            id=report.id,
            category=report.category,
            subject_type=report.subject_type,
            subject_id=report.subject_id,
            description=report.description.value,
            status=report.status.value,
            created_at=report.created_at,
        )
