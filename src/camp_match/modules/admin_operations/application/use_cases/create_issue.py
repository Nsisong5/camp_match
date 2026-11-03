from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.application.errors import (
    IdempotencyKeyConflict,
)
from camp_match.modules.admin_operations.application.ports.inbound import IssueView
from camp_match.modules.admin_operations.domain.entities import (
    IssueEvent,
    OperationalIssue,
)
from camp_match.modules.admin_operations.domain.value_objects import (
    IssueCategory,
    IssuePriority,
    IssueStatus,
    ReferenceType,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class CreateIssueUseCase:
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
        category: IssueCategory,
        title: str,
        description: str,
        priority: IssuePriority,
        references: tuple[tuple[ReferenceType, EntityId], ...],
        idempotency_key: str,
    ) -> IssueView:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_ISSUES_MANAGE)

        now = self._clock.now()
        issue_id = EntityId.new()
        existing = await self._issue_repo.get_by_idempotency(actor_id, idempotency_key)
        if existing:
            raise IdempotencyKeyConflict("Duplicate idempotency key for user.")

        issue = OperationalIssue(
            id=issue_id,
            category=category,
            title=title,
            description=description,
            priority=priority,
            status=IssueStatus.OPEN,
            assignee_id=None,
            references=references,
            created_by=actor_id,
            idempotency_key=idempotency_key,
            version=1,
            created_at=now,
            updated_at=now,
        )

        event = IssueEvent(
            id=EntityId.new(),
            issue_id=issue_id,
            event_type="CREATED",
            actor_id=actor_id,
            occurred_at=now,
            details={"title": title, "category": category.value},
        )

        async with self._uow_factory() as uow:
            await self._issue_repo.add(issue)
            await self._issue_repo.add_event(event)
            await uow.commit()

        return IssueView(
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
