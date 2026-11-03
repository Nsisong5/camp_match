from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.application.ports.inbound import (
    IssueView,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class ListIssuesUseCase:
    def __init__(self, issue_repo: Any, authorizer: Any) -> None:
        self._issue_repo = issue_repo
        self._authorizer = authorizer

    async def execute(
        self,
        actor_id: EntityId,
        status: Any | None = None,
        assignee_id: EntityId | None = None,
        priority: Any | None = None,
        category: Any | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[IssueView]:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_ISSUES_MANAGE)
        req = page_request or PageRequest(page=1, page_size=20)
        page = await self._issue_repo.list(
            status=status,
            assignee_id=assignee_id,
            priority=priority,
            category=category,
            page_request=req,
        )
        items = [
            IssueView(
                id=i.id,
                category=i.category,
                title=i.title,
                description=i.description,
                priority=i.priority,
                status=i.status,
                assignee_id=i.assignee_id,
                references=i.references,
                created_by=i.created_by,
                idempotency_key=i.idempotency_key,
                version=i.version,
                created_at=i.created_at,
                updated_at=i.updated_at,
                resolved_at=i.resolved_at,
                resolution_summary=i.resolution_summary,
            )
            for i in page.items
        ]
        return Page(
            items=items,
            total=page.total,
            page=page.page,
            page_size=page.page_size,
        )
