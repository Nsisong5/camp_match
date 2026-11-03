"""SQLAlchemy inbox repository adapter."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from camp_match.modules.notification.adapters.persistence.models import InboxModel
from camp_match.modules.notification.application.ports.inbound import InboxRow
from camp_match.modules.notification.domain.value_objects import InboxStatus


class SqlAlchemyInboxRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def add(
        self, event_id: str, event_type: str, payload: dict[str, Any], now: datetime
    ) -> bool:
        eid = (
            UUID(event_id)
            if isinstance(event_id, str)
            else event_id
        )
        stmt = (
            insert(InboxModel)
            .values(
                event_id=eid,
                event_type=event_type,
                payload=payload,
                received_at=now,
                status="PENDING",
                attempts=0,
                next_attempt_at=now,
            )
            .on_conflict_do_nothing(index_elements=["event_id"])
            .returning(InboxModel.event_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def claim(self, event_id: str) -> InboxRow | None:
        eid = (
            UUID(event_id)
            if isinstance(event_id, str)
            else event_id
        )
        stmt = (
            select(InboxModel)
            .where(
                InboxModel.event_id == eid,
                InboxModel.status == "PENDING",
            )
            .with_for_update(skip_locked=True)
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        if not model:
            return None
        return InboxRow(
            event_id=str(model.event_id),
            event_type=model.event_type,
            payload=model.payload,
            attempts=model.attempts,
        )

    async def mark_processed(self, event_id: str, now: datetime) -> None:
        eid = (
            UUID(event_id)
            if isinstance(event_id, str)
            else event_id
        )
        stmt = (
            update(InboxModel)
            .where(InboxModel.event_id == eid)
            .values(status="PROCESSED", processed_at=now)
        )
        await self.session.execute(stmt)

    async def mark_rejected(self, event_id: str, code: str, now: datetime) -> None:
        eid = (
            UUID(event_id)
            if isinstance(event_id, str)
            else event_id
        )
        stmt = (
            update(InboxModel)
            .where(InboxModel.event_id == eid)
            .values(status="REJECTED", last_error=code, processed_at=now)
        )
        await self.session.execute(stmt)

    async def record_failure(
        self,
        event_id: str,
        error_class: str,
        next_attempt_at: datetime,
        dead: bool,
    ) -> None:
        eid = (
            UUID(event_id)
            if isinstance(event_id, str)
            else event_id
        )
        status_val = "DEAD" if dead else "PENDING"
        stmt = (
            update(InboxModel)
            .where(InboxModel.event_id == eid)
            .values(
                attempts=InboxModel.attempts + 1,
                last_error=error_class,
                next_attempt_at=next_attempt_at,
                status=status_val,
            )
        )
        await self.session.execute(stmt)

    async def list_due(self, now: datetime, limit: int) -> list[str]:
        stmt = (
            select(InboxModel.event_id)
            .where(
                InboxModel.status == "PENDING",
                InboxModel.next_attempt_at <= now,
            )
            .order_by(InboxModel.next_attempt_at.asc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return [str(eid) for eid in res.scalars().all()]

    async def requeue_dead(self) -> int:
        stmt = (
            update(InboxModel)
            .where(InboxModel.status == "DEAD")
            .values(status="PENDING", attempts=0)
        )
        res = await self.session.execute(stmt)
        return int(res.rowcount)

    async def stats(self) -> dict[InboxStatus, int]:
        stmt = select(InboxModel.status, func.count()).group_by(InboxModel.status)
        res = await self.session.execute(stmt)
        data = {InboxStatus(row[0]): row[1] for row in res.all()}
        return {st: data.get(st, 0) for st in InboxStatus}
