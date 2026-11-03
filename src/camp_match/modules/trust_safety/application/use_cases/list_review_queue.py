"""List review queue use case for Trust & Safety."""
from __future__ import annotations

from typing import Any

from camp_match.modules.security.domain.value_objects import Permission
from camp_match.modules.trust_safety.application.ports.inbound import (
    ListReviewQueueRequest,
    ReviewerReportView,
)
from camp_match.shared_kernel.application.pagination import Page


class ListReviewQueueUseCase:
    def __init__(self, report_repo: Any, auth_service: Any) -> None:
        self._report_repo = report_repo
        self._auth = auth_service

    async def execute(self, request: ListReviewQueueRequest) -> Page[ReviewerReportView]:
        await self._auth.authorize(request.actor_id, Permission.SAFETY_CASE_REVIEW)
        page = await self._report_repo.list_unlinked(
            category=request.category,
            page_request=request.page_request,
        )
        views = [
            ReviewerReportView(
                id=r.id,
                reporter_id=r.reporter_id,
                category=r.category,
                subject_type=r.subject_type,
                subject_id=r.subject_id,
                description=r.description.value,
                status=r.status,
                case_id=None,
                similar_report_count=await self._report_repo.similar_report_count(r.subject_type, r.subject_id, r.id),
                created_at=r.created_at,
            )
            for r in page.items
        ]
        return Page(items=views, total=page.total, page=page.page, page_size=page.page_size)
