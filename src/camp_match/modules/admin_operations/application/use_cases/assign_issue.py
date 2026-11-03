from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.application.errors import (
    IssueNotFound,
    IssueStateChanged,
)
from camp_match.modules.admin_operations.application.ports.inbound import (
    IssueView,
)
from camp_match.modules.admin_operations.domain.entities import IssueEvent
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class AssignIssueUseCase:
    def __init__(
        self,
        issue_repo: Any,
        authorizer: Any,
        uow_factory: Any,
        clock: Any,
    ) -> None:
        self._issue_repo = issue_repo
        self._authorizer = authorizer
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(
        self,
        actor_id: EntityId,
        issue_id: EntityId,
        assignee_id: EntityId | None,
        version: int,
    ) -> IssueView:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_ISSUES_MANAGE)

        if assignee_id is not None:
            await self._authorizer.authorize(
                assignee_id, Permission.ADMIN_ISSUES_MANAGE
            )

        issue = await self._issue_repo.get(issue_id)
        if not issue:
            raise IssueNotFound(f"Issue {issue_id} not found.")

        now = self._clock.now()

        event = IssueEvent(
            id=EntityId.new(),
            issue_id=issue_id,
            event_type="ASSIGNED",
            actor_id=actor_id,
            occurred_at=now,
            details={
                "assignee_id": str(assignee_id.value) if assignee_id else None
            },
        )

        async with self._uow_factory() as uow:
            success = await self._issue_repo.update_assignee(
                issue_id, assignee_id, expected_version=version, now=now
            )
            if not success:
                raise IssueStateChanged(
                    "Issue state changed concurrently (stale version)."
                )
            await self._issue_repo.add_event(event)
            await uow.commit()

        final_issue = await self._issue_repo.get(issue_id)
        assert final_issue is not None
        return IssueView(
            id=final_issue.id,
            category=final_issue.category,
            title=final_issue.title,
            description=final_issue.description,
            priority=final_issue.priority,
            status=final_issue.status,
            assignee_id=final_issue.assignee_id,
            references=final_issue.references,
            created_by=final_issue.created_by,
            idempotency_key=final_issue.idempotency_key,
            version=final_issue.version,
            created_at=final_issue.created_at,
            updated_at=final_issue.updated_at,
            resolved_at=final_issue.resolved_at,
            resolution_summary=final_issue.resolution_summary,
        )
