from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.modules.admin_operations.adapters.persistence.models import (
    AdminAuditEventModel,
)
from camp_match.modules.admin_operations.application.ports.outbound import (
    AuditRepository,
)
from camp_match.modules.admin_operations.domain.entities import AuditEvent
from camp_match.modules.admin_operations.domain.value_objects import (
    AdminActionType,
    AuditEventType,
    AuditTargetType,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class SqlAlchemyAuditRepository(AuditRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: AuditEvent) -> None:
        model = AdminAuditEventModel(
            id=event.id.value,
            action_id=event.action_id.value,
            event_type=event.event_type.value,
            action_type=event.action_type.value,
            actor_id=event.actor_id.value,
            target_type=event.target_type.value,
            target_id=event.target_id.value if event.target_id else None,
            reason=event.reason,
            outcome_code=event.outcome_code,
            occurred_at=event.occurred_at,
            request_id=event.request_id,
            details=event.details,
        )
        self._session.add(model)
        await self._session.flush()

    async def list(
        self,
        actor_id: EntityId | None = None,
        action_type: AdminActionType | None = None,
        target_id: EntityId | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[AuditEvent]:
        req = page_request or PageRequest(page=1, page_size=20)
        query = select(AdminAuditEventModel)
        count_query = select(func.count()).select_from(AdminAuditEventModel)

        if actor_id:
            query = query.where(
                AdminAuditEventModel.actor_id == actor_id.value
            )
            count_query = count_query.where(
                AdminAuditEventModel.actor_id == actor_id.value
            )
        if action_type:
            query = query.where(
                AdminAuditEventModel.action_type == action_type.value
            )
            count_query = count_query.where(
                AdminAuditEventModel.action_type == action_type.value
            )
        if target_id:
            query = query.where(
                AdminAuditEventModel.target_id == target_id.value
            )
            count_query = count_query.where(
                AdminAuditEventModel.target_id == target_id.value
            )
        if from_date:
            query = query.where(AdminAuditEventModel.occurred_at >= from_date)
            count_query = count_query.where(
                AdminAuditEventModel.occurred_at >= from_date
            )
        if to_date:
            query = query.where(AdminAuditEventModel.occurred_at <= to_date)
            count_query = count_query.where(
                AdminAuditEventModel.occurred_at <= to_date
            )

        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        query = (
            query.order_by(
                AdminAuditEventModel.occurred_at.desc(),
                AdminAuditEventModel.id.desc(),
            )
            .offset((req.page - 1) * req.page_size)
            .limit(req.page_size)
        )
        result = await self._session.execute(query)
        models = result.scalars().all()
        items = [self._to_domain(m) for m in models]

        return Page(
            items=items, total=total, page=req.page, page_size=req.page_size
        )

    async def count_uncertain(
        self, cutoff: datetime
    ) -> tuple[int, datetime | None]:
        subq = select(AdminAuditEventModel.action_id).where(
            AdminAuditEventModel.event_type.in_([
                AuditEventType.ACTION_SUCCEEDED.value,
                AuditEventType.ACTION_FAILED.value,
            ])
        )

        stmt = select(
            func.count(AdminAuditEventModel.id),
            func.min(AdminAuditEventModel.occurred_at),
        ).where(
            AdminAuditEventModel.event_type
            == AuditEventType.ACTION_REQUESTED.value,
            AdminAuditEventModel.occurred_at < cutoff,
            ~AdminAuditEventModel.action_id.in_(subq),
        )

        result = await self._session.execute(stmt)
        row = result.first()
        if not row or row[0] == 0:
            return (0, None)
        return (row[0], row[1])

    def _to_domain(self, model: AdminAuditEventModel) -> AuditEvent:
        return AuditEvent(
            id=EntityId(model.id),
            action_id=EntityId(model.action_id),
            event_type=AuditEventType(model.event_type),
            action_type=AdminActionType(model.action_type),
            actor_id=EntityId(model.actor_id),
            target_type=AuditTargetType(model.target_type),
            target_id=EntityId(model.target_id) if model.target_id else None,
            reason=model.reason,
            outcome_code=model.outcome_code,
            occurred_at=model.occurred_at,
            request_id=model.request_id,
            details=model.details,
        )
