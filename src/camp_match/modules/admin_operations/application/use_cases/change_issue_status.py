from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.adapters.persistence.issue_repository import (
    SqlAlchemyIssueRepository,
)
from camp_match.modules.admin_operations.application.errors import (
    IssueNotFound,
    IssueStateChanged,
)
from camp_match.modules.admin_operations.application.ports.inbound import (
    IssueView,
)
from camp_match.modules.admin_operations.domain.entities import IssueEvent
from camp_match.modules.admin_operations.domain.value_objects import IssueStatus
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class ChangeIssueStatusUseCase:
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
        new_status: IssueStatus,
        version: int,
        reason: str | None = None,
        resolution_summary: str | None = None,
    ) -> IssueView:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_ISSUES_MANAGE)

        issue = await self._issue_repo.get(issue_id)
        if not issue:
            raise IssueNotFound(f"Issue {issue_id} not found.")

        old_status = issue.status
        now = self._clock.now()
        issue.transition_to(
            new_status,
            reason=reason,
            resolution_summary=resolution_summary,
            now=now,
        )

        event = IssueEvent(
            id=EntityId.new(),
            issue_id=issue_id,
            event_type="STATUS_CHANGED",
            actor_id=actor_id,
            occurred_at=now,
            details={
                "from": old_status.value,
                "to": new_status.value,
                "reason": reason,
                "resolution_summary": resolution_summary,
            },
        )

        async with self._uow_factory() as session:
            repo = SqlAlchemyIssueRepository(session)
            success = await repo.update_status(
                issue_id,
                new_status,
                expected_version=version,
                now=now,
                resolution_summary=resolution_summary,
            )
            if not success:
                raise IssueStateChanged(
                    "Issue state changed concurrently (stale version)."
                )
            await repo.add_event(event)
            await session.commit()

        async with self._uow_factory() as session:
            repo = SqlAlchemyIssueRepository(session)
            final_issue = await repo.get(issue_id)
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
