"""List my reports use case for Trust & Safety."""
from __future__ import annotations

from camp_match.modules.trust_safety.application.ports.inbound import (
    ListMyReportsRequest,
    ReporterReportView,
)
from camp_match.modules.trust_safety.application.ports.outbound import ReportRepository
from camp_match.shared_kernel.application.pagination import Page


class ListMyReportsUseCase:
    def __init__(self, report_repo: ReportRepository) -> None:
        self._report_repo = report_repo

    async def execute(self, request: ListMyReportsRequest) -> Page[ReporterReportView]:
        page = await self._report_repo.list_by_reporter(request.actor_id, request.page_request)
        views = [
            ReporterReportView(
                id=r.id,
                category=r.category,
                subject_type=r.subject_type,
                subject_id=r.subject_id,
                description=r.description.value,
                status=r.status.value,
                created_at=r.created_at,
            )
            for r in page.items
        ]
        return Page(items=views, total=page.total, page=page.page, page_size=page.page_size)
