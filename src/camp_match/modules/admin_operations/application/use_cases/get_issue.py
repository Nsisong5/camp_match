from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.application.errors import IssueNotFound
from camp_match.modules.admin_operations.application.ports.inbound import (
    IssueDetailView,
    IssueEventView,
    IssueView,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class GetIssueUseCase:
    def __init__(self, issue_repo: Any, authorizer: Any) -> None:
        self._issue_repo = issue_repo
        self._authorizer = authorizer

    async def execute(
        self, actor_id: EntityId, issue_id: EntityId
    ) -> IssueDetailView:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_ISSUES_MANAGE)
        issue = await self._issue_repo.get(issue_id)
        if not issue:
            raise IssueNotFound(f"Issue {issue_id} not found.")

        events = await self._issue_repo.list_events(issue_id)
        issue_view = IssueView(
            id=issue.id,
            category=issue.category,
            title=issue.title,
            description=issue.description,
            priority=issue.priority,
            status=issue.status,
            assignee_id=issue.assignee_id,
            references=issue.references,
            created_by=issue.created_by,
            idempotency_key=issue.idempotency_key,
            version=issue.version,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            resolved_at=issue.resolved_at,
            resolution_summary=issue.resolution_summary,
        )
        history = [
            IssueEventView(
                id=e.id,
                issue_id=e.issue_id,
                event_type=e.event_type,
                actor_id=e.actor_id,
                occurred_at=e.occurred_at,
                details=e.details,
            )
            for e in events
        ]
        return IssueDetailView(issue=issue_view, history=history)
