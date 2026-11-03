from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update

from camp_match.modules.messaging.adapters.persistence.models import MessagingOutboxModel
from camp_match.modules.messaging.domain.events import MessageCreated
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: MessageCreated) -> None:
        model = MessagingOutboxModel(
            id=event.event_id.value,
            event_type="MessageCreated",
            payload=event.to_payload(),
            occurred_at=event.occurred_at or datetime.now(),
            dispatched_at=None,
            attempts=0,
            last_error=None,
        )
        self._session.add(model)
        await self._session.flush()

    async def get(self, event_id: EntityId) -> MessageCreated | None:
        stmt = select(MessagingOutboxModel).where(MessagingOutboxModel.id == event_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def claim_pending(self, limit: int) -> list[MessageCreated]:
        stmt = (
            select(MessagingOutboxModel)
            .where(MessagingOutboxModel.dispatched_at.is_(None))
            .order_by(MessagingOutboxModel.occurred_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def mark_dispatched(self, event_id: EntityId, at: datetime) -> None:
        stmt = (
            update(MessagingOutboxModel)
            .where(MessagingOutboxModel.id == event_id.value)
            .values(dispatched_at=at)
        )
        await self._session.execute(stmt)

    async def record_failure(self, event_id: EntityId, error_class_name: str) -> None:
        stmt = (
            update(MessagingOutboxModel)
            .where(MessagingOutboxModel.id == event_id.value)
            .values(
                attempts=MessagingOutboxModel.attempts + 1,
                last_error=error_class_name,
            )
        )
        await self._session.execute(stmt)

    async def get_outbox_stats(self, clock: Any) -> tuple[int, int | None]:
        count_stmt = select(func.count(MessagingOutboxModel.id)).where(
            MessagingOutboxModel.dispatched_at.is_(None)
        )
        total_result = await self._session.execute(count_stmt)
        pending = total_result.scalar_one()

        if pending == 0:
            return (0, None)

        oldest_stmt = (
            select(MessagingOutboxModel.occurred_at)
            .where(MessagingOutboxModel.dispatched_at.is_(None))
            .order_by(MessagingOutboxModel.occurred_at.asc())
            .limit(1)
        )
        oldest_result = await self._session.execute(oldest_stmt)
        oldest_at = oldest_result.scalar_one_or_none()

        if not oldest_at:
            return (pending, None)

        now = clock.now()
        age_seconds = int((now - oldest_at).total_seconds())
        return (pending, max(0, age_seconds))

    def _to_domain(self, model: MessagingOutboxModel) -> MessageCreated:
        return MessageCreated.from_payload(model.payload)
