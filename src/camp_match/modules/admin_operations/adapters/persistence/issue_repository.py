from __future__ import annotations

import builtins
import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.modules.admin_operations.adapters.persistence.models import (
    AdminIssueEventModel,
    AdminIssueModel,
)
from camp_match.modules.admin_operations.application.errors import IdempotencyKeyConflict
from camp_match.modules.admin_operations.application.ports.outbound import IssueRepository
from camp_match.modules.admin_operations.domain.entities import IssueEvent, OperationalIssue
from camp_match.modules.admin_operations.domain.value_objects import (
    IssueCategory,
    IssuePriority,
    IssueStatus,
    ReferenceType,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class SqlAlchemyIssueRepository(IssueRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, issue: OperationalIssue) -> None:
        model = AdminIssueModel(
            id=issue.id.value,
            category=issue.category.value,
            title=issue.title,
            description=issue.description,
            priority=issue.priority.value,
            status=issue.status.value,
            assignee_id=issue.assignee_id.value if issue.assignee_id else None,
            references=[[r[0].value, str(r[1].value)] for r in issue.references],
            created_by=issue.created_by.value,
            idempotency_key=issue.idempotency_key,
            version=issue.version,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            resolved_at=issue.resolved_at,
            resolution_summary=issue.resolution_summary,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as e:
            if "uq_admin_issues_created_by_idempotency_key" in str(e):
                raise IdempotencyKeyConflict("Duplicate idempotency key for user.") from e
            raise

    async def get(self, issue_id: EntityId) -> OperationalIssue | None:
        stmt = select(AdminIssueModel).where(AdminIssueModel.id == issue_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_domain(model)

    async def get_by_idempotency(
        self, created_by: EntityId, idempotency_key: str
    ) -> OperationalIssue | None:
        stmt = select(AdminIssueModel).where(
            AdminIssueModel.created_by == created_by.value,
            AdminIssueModel.idempotency_key == idempotency_key,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_domain(model)

    async def list(
        self,
        status: IssueStatus | None = None,
        assignee_id: EntityId | None = None,
        priority: IssuePriority | None = None,
        category: IssueCategory | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[OperationalIssue]:
        req = page_request or PageRequest(page=1, page_size=20)
        query = select(AdminIssueModel)
        count_query = select(func.count()).select_from(AdminIssueModel)

        if status:
            query = query.where(AdminIssueModel.status == status.value)
            count_query = count_query.where(AdminIssueModel.status == status.value)
        if assignee_id:
            query = query.where(AdminIssueModel.assignee_id == assignee_id.value)
            count_query = count_query.where(AdminIssueModel.assignee_id == assignee_id.value)
        if priority:
            query = query.where(AdminIssueModel.priority == priority.value)
            count_query = count_query.where(AdminIssueModel.priority == priority.value)
        if category:
            query = query.where(AdminIssueModel.category == category.value)
            count_query = count_query.where(AdminIssueModel.category == category.value)

        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        query = (
            query.order_by(AdminIssueModel.created_at.desc())
            .offset((req.page - 1) * req.page_size)
            .limit(req.page_size)
        )
        result = await self._session.execute(query)
        models = result.scalars().all()
        items = [self._to_domain(m) for m in models]

        return Page(items=items, total=total, page=req.page, page_size=req.page_size)

    async def update_status(
        self,
        issue_id: EntityId,
        new_status: IssueStatus,
        expected_version: int,
        now: datetime,
        resolution_summary: str | None = None,
    ) -> bool:
        values: dict[str, Any] = {
            "status": new_status.value,
            "version": AdminIssueModel.version + 1,
            "updated_at": now,
        }
        if resolution_summary is not None:
            values["resolution_summary"] = resolution_summary
        if new_status == IssueStatus.RESOLVED:
            values["resolved_at"] = now
        elif new_status == IssueStatus.CLOSED:
            values["resolved_at"] = None

        stmt = (
            update(AdminIssueModel)
            .where(
                AdminIssueModel.id == issue_id.value,
                AdminIssueModel.version == expected_version,
            )
            .values(**values)
        )
        result = await self._session.execute(stmt)
        return bool(cast(Any, result).rowcount == 1)

    async def update_assignee(
        self,
        issue_id: EntityId,
        assignee_id: EntityId | None,
        expected_version: int,
        now: datetime,
    ) -> bool:
        stmt = (
            update(AdminIssueModel)
            .where(
                AdminIssueModel.id == issue_id.value,
                AdminIssueModel.version == expected_version,
            )
            .values(
                assignee_id=assignee_id.value if assignee_id else None,
                version=AdminIssueModel.version + 1,
                updated_at=now,
            )
        )
        result = await self._session.execute(stmt)
        return bool(cast(Any, result).rowcount == 1)

    async def add_event(self, event: IssueEvent) -> None:
        model = AdminIssueEventModel(
            id=event.id.value,
            issue_id=event.issue_id.value,
            event_type=event.event_type,
            actor_id=event.actor_id.value,
            occurred_at=event.occurred_at,
            details=event.details,
        )
        self._session.add(model)
        await self._session.flush()

    async def list_events(self, issue_id: EntityId) -> builtins.list[IssueEvent]:
        stmt = (
            select(AdminIssueEventModel)
            .where(AdminIssueEventModel.issue_id == issue_id.value)
            .order_by(AdminIssueEventModel.occurred_at.asc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [
            IssueEvent(
                id=EntityId(m.id),
                issue_id=EntityId(m.issue_id),
                event_type=m.event_type,
                actor_id=EntityId(m.actor_id),
                occurred_at=m.occurred_at,
                details=m.details,
            )
            for m in models
        ]

    async def counts_by_status(self) -> dict[str, int]:
        stmt = select(AdminIssueModel.status, func.count(AdminIssueModel.id)).group_by(
            AdminIssueModel.status
        )
        result = await self._session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def count_unassigned_open(self) -> int:
        stmt = select(func.count(AdminIssueModel.id)).where(
            AdminIssueModel.status == IssueStatus.OPEN.value,
            AdminIssueModel.assignee_id.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def count_high_priority_open(self) -> int:
        stmt = select(func.count(AdminIssueModel.id)).where(
            AdminIssueModel.status != IssueStatus.CLOSED.value,
            AdminIssueModel.priority.in_([IssuePriority.HIGH.value, IssuePriority.URGENT.value]),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    def _to_domain(self, model: AdminIssueModel) -> OperationalIssue:
        refs = tuple(
            (ReferenceType(r[0]), EntityId(uuid.UUID(r[1]))) for r in model.references
        )
        return OperationalIssue(
            id=EntityId(model.id),
            category=IssueCategory(model.category),
            title=model.title,
            description=model.description,
            priority=IssuePriority(model.priority),
            status=IssueStatus(model.status),
            assignee_id=EntityId(model.assignee_id) if model.assignee_id else None,
            references=refs,
            created_by=EntityId(model.created_by),
            idempotency_key=model.idempotency_key,
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
            resolved_at=model.resolved_at,
            resolution_summary=model.resolution_summary,
        )
