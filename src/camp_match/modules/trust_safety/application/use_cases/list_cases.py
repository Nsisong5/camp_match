"""List cases use case for Trust & Safety."""
from __future__ import annotations

from typing import Any

from camp_match.modules.security.domain.value_objects import Permission
from camp_match.modules.trust_safety.application.ports.inbound import (
    ListCasesRequest,
    ReviewerCaseView,
)
from camp_match.shared_kernel.application.pagination import Page


class ListCasesUseCase:
    def __init__(self, case_repo: Any, auth_service: Any) -> None:
        self._case_repo = case_repo
        self._auth = auth_service

    async def execute(self, request: ListCasesRequest) -> Page[ReviewerCaseView]:
        await self._auth.authorize(request.actor_id, Permission.SAFETY_CASE_REVIEW)
        page = await self._case_repo.list_cases(
            status=request.status,
            category=request.category,
            assigned_to=request.assigned_to,
            page_request=request.page_request,
        )
        views = []
        for c in page.items:
            views.append(
                ReviewerCaseView(
                    id=c.id,
                    category=c.category,
                    priority=c.priority,
                    status=c.status,
                    subject_user_id=c.subject_user_id,
                    assigned_to=c.assigned_to,
                    version=c.version,
                    cycle=c.cycle,
                    created_by=c.created_by,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                    resolved_at=c.resolved_at,
                    closed_at=c.closed_at,
                    linked_reports=tuple(),
                    evidence_metadata=tuple(),
                    notes=tuple(),
                    decisions=tuple(),
                    enforcement_actions=tuple(),
                    viewer_kind="REVIEWER",
                )
            )
        return Page(items=views, total=page.total, page=page.page, page_size=page.page_size)
