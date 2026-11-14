from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.modules.platform_runtime.adapters.persistence.models import PlatformOutboxModel
from camp_match.modules.platform_runtime.application.ports.outbound import OutboxRecord
from camp_match.shared_kernel.domain.identifiers import EntityId


class SqlAlchemyOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        event_id: EntityId,
        event_type: str,
        payload: dict[str, Any],
        occurred_at: datetime,
        created_at: datetime,
        next_attempt_at: datetime,
    ) -> None:
        stmt = insert(PlatformOutboxModel).values(
            event_id=event_id.value,
            event_type=event_type,
            payload=payload,
            occurred_at=occurred_at,
            created_at=created_at,
            status="PENDING",
            attempts=0,
            next_attempt_at=next_attempt_at,
        ).on_conflict_do_nothing(index_elements=["event_id"])
        await self._session.execute(stmt)

    async def claim_due(self, limit: int, now: datetime) -> list[OutboxRecord]:
        stmt = (
            select(PlatformOutboxModel)
            .where(
                PlatformOutboxModel.status == "PENDING",
                PlatformOutboxModel.next_attempt_at <= now,
            )
            .order_by(PlatformOutboxModel.next_attempt_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [
            OutboxRecord(
                event_id=EntityId(m.event_id),
                event_type=m.event_type,
                payload=m.payload,
                occurred_at=m.occurred_at,
                attempts=m.attempts,
            )
            for m in models
        ]

    async def get_by_ids(self, event_ids: list[EntityId]) -> list[OutboxRecord]:
        if not event_ids:
            return []
        uuid_vals = [eid.value for eid in event_ids]
        stmt = select(PlatformOutboxModel).where(
            PlatformOutboxModel.event_id.in_(uuid_vals),
            PlatformOutboxModel.status == "PENDING",
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [
            OutboxRecord(
                event_id=EntityId(m.event_id),
                event_type=m.event_type,
                payload=m.payload,
                occurred_at=m.occurred_at,
                attempts=m.attempts,
            )
            for m in models
        ]

    async def mark_delivered(self, event_id: EntityId, delivered_at: datetime) -> None:
        stmt = (
            update(PlatformOutboxModel)
            .where(PlatformOutboxModel.event_id == event_id.value)
            .values(status="DELIVERED", delivered_at=delivered_at)
        )
        await self._session.execute(stmt)

    async def record_failure(
        self,
        event_id: EntityId,
        attempts: int,
        next_attempt_at: datetime,
        last_error: str,
    ) -> None:
        stmt = (
            update(PlatformOutboxModel)
            .where(PlatformOutboxModel.event_id == event_id.value)
            .values(
                attempts=attempts,
                next_attempt_at=next_attempt_at,
                last_error=last_error[:255],
            )
        )
        await self._session.execute(stmt)

    async def mark_dead(
        self,
        event_id: EntityId,
        last_error: str,
        now: datetime,
        attempts: int,
    ) -> None:
        stmt = (
            update(PlatformOutboxModel)
            .where(PlatformOutboxModel.event_id == event_id.value)
            .values(
                status="DEAD",
                attempts=attempts,
                last_error=last_error[:255],
                next_attempt_at=now,
            )
        )
        await self._session.execute(stmt)

    async def requeue_dead(self, now: datetime) -> int:
        stmt = (
            update(PlatformOutboxModel)
            .where(PlatformOutboxModel.status == "DEAD")
            .values(
                status="PENDING",
                attempts=0,
                last_error=None,
                next_attempt_at=now,
            )
        )
        res = await self._session.execute(stmt)
        return int(res.rowcount)

    async def purge_delivered(self, cutoff: datetime, limit: int) -> int:
        subq = (
            select(PlatformOutboxModel.event_id)
            .where(
                PlatformOutboxModel.status == "DELIVERED",
                PlatformOutboxModel.delivered_at < cutoff,
            )
            .limit(limit)
            .scalar_subquery()
        )
        stmt = delete(PlatformOutboxModel).where(PlatformOutboxModel.event_id.in_(subq))
        res = await self._session.execute(stmt)
        return int(res.rowcount)
