"""SQLAlchemy notification repository adapter."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text, update

from camp_match.modules.notification.adapters.persistence.models import NotificationModel
from camp_match.modules.notification.application.ports.inbound import CreateOutcome
from camp_match.modules.notification.domain.entities import Notification
from camp_match.modules.notification.domain.value_objects import (
    NotificationCategory,
    NotificationTarget,
    NotificationType,
    TargetType,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


def _to_entity(model: NotificationModel) -> Notification:
    target = None
    if model.target_type and model.target_id:
        target = NotificationTarget(
            type=TargetType(model.target_type),
            id=EntityId(model.target_id),
        )
    return Notification(
        id=EntityId(model.id),
        recipient_id=EntityId(model.recipient_id),
        type=NotificationType(model.type),
        category=NotificationCategory(model.category),
        title=model.title,
        body=model.body,
        target=target,
        group_key=model.group_key,
        event_count=model.event_count,
        source_event_id=str(model.source_event_id),
        created_at=model.created_at,
        latest_event_at=model.latest_event_at,
        read_at=model.read_at,
    )


class SqlAlchemyNotificationRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def create_or_collapse(self, notification: Notification) -> CreateOutcome:
        if notification.group_key is not None and notification.type.is_collapsible:
            stmt = text(
                """
                INSERT INTO notification_notifications (
                    id, recipient_id, type, category, title, body,
                    target_type, target_id, group_key, event_count,
                    source_event_id, created_at, latest_event_at, read_at
                ) VALUES (
                    :id, :recipient_id, :type, :category, :title, :body,
                    :target_type, :target_id, :group_key, 1,
                    :source_event_id, :created_at, :latest_event_at, NULL
                )
                ON CONFLICT (recipient_id, group_key)
                WHERE group_key IS NOT NULL AND read_at IS NULL
                DO UPDATE SET
                    event_count = notification_notifications.event_count + 1,
                    latest_event_at = GREATEST(
                        notification_notifications.latest_event_at,
                        :latest_event_at
                    )
                RETURNING (xmax = 0) AS inserted;
                """
            )
            target_type_val = (
                notification.target.type.value if notification.target else None
            )
            target_id_val = (
                notification.target.id.value if notification.target else None
            )
            source_event_id_uuid = (
                UUID(notification.source_event_id)
                if isinstance(notification.source_event_id, str)
                else notification.source_event_id
            )
            res = await self.session.execute(
                stmt,
                {
                    "id": notification.id.value,
                    "recipient_id": notification.recipient_id.value,
                    "type": notification.type.value,
                    "category": notification.category.value,
                    "title": notification.title,
                    "body": notification.body,
                    "target_type": target_type_val,
                    "target_id": target_id_val,
                    "group_key": notification.group_key,
                    "source_event_id": source_event_id_uuid,
                    "created_at": notification.created_at,
                    "latest_event_at": notification.latest_event_at,
                },
            )
            inserted = res.scalar_one()
            return CreateOutcome.CREATED if inserted else CreateOutcome.COLLAPSED
        else:
            target_type_val = (
                notification.target.type.value if notification.target else None
            )
            target_id_val = (
                notification.target.id.value if notification.target else None
            )
            source_event_id_uuid = (
                UUID(notification.source_event_id)
                if isinstance(notification.source_event_id, str)
                else notification.source_event_id
            )
            model = NotificationModel(
                id=notification.id.value,
                recipient_id=notification.recipient_id.value,
                type=notification.type.value,
                category=notification.category.value,
                title=notification.title,
                body=notification.body,
                target_type=target_type_val,
                target_id=target_id_val,
                group_key=notification.group_key,
                event_count=notification.event_count,
                source_event_id=source_event_id_uuid,
                created_at=notification.created_at,
                latest_event_at=notification.latest_event_at,
                read_at=notification.read_at,
            )
            self.session.add(model)
            await self.session.flush()
            return CreateOutcome.CREATED

    async def list_for_recipient(
        self,
        recipient_id: EntityId,
        unread_only: bool | None,
        category: NotificationCategory | None,
        page_request: PageRequest,
    ) -> Page[Notification]:
        stmt = select(NotificationModel).where(
            NotificationModel.recipient_id == recipient_id.value
        )
        if unread_only:
            stmt = stmt.where(NotificationModel.read_at.is_(None))
        if category:
            stmt = stmt.where(NotificationModel.category == category.value)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.session.execute(count_stmt)
        total = int(total_res.scalar_one())

        # Ordering & Pagination
        offset = (page_request.page - 1) * page_request.page_size
        stmt = (
            stmt.order_by(
                NotificationModel.latest_event_at.desc(),
                NotificationModel.id.desc(),
            )
            .offset(offset)
            .limit(page_request.page_size)
        )

        res = await self.session.execute(stmt)
        models = res.scalars().all()
        items = [_to_entity(m) for m in models]

        return Page(
            items=items,
            total=total,
            page=page_request.page,
            page_size=page_request.page_size,
        )

    async def count_unread(self, recipient_id: EntityId) -> int:
        stmt = select(func.count()).select_from(NotificationModel).where(
            NotificationModel.recipient_id == recipient_id.value,
            NotificationModel.read_at.is_(None),
        )
        res = await self.session.execute(stmt)
        return int(res.scalar_one())

    async def get_by_id(
        self, notification_id: EntityId, recipient_id: EntityId
    ) -> Notification | None:
        stmt = select(NotificationModel).where(
            NotificationModel.id == notification_id.value,
            NotificationModel.recipient_id == recipient_id.value,
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def mark_read(
        self, notification_id: EntityId, recipient_id: EntityId, now: datetime
    ) -> bool:
        stmt = (
            update(NotificationModel)
            .where(
                NotificationModel.id == notification_id.value,
                NotificationModel.recipient_id == recipient_id.value,
                NotificationModel.read_at.is_(None),
            )
            .values(read_at=now)
        )
        res = await self.session.execute(stmt)
        return bool(res.rowcount == 1)

    async def exists_for_recipient(
        self, notification_id: EntityId, recipient_id: EntityId
    ) -> bool:
        stmt = select(NotificationModel.id).where(
            NotificationModel.id == notification_id.value,
            NotificationModel.recipient_id == recipient_id.value,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def mark_all_read(
        self,
        recipient_id: EntityId,
        category: NotificationCategory | None,
        now: datetime,
    ) -> int:
        stmt = update(NotificationModel).where(
            NotificationModel.recipient_id == recipient_id.value,
            NotificationModel.read_at.is_(None),
        )
        if category:
            stmt = stmt.where(NotificationModel.category == category.value)
        stmt = stmt.values(read_at=now)
        res = await self.session.execute(stmt)
        return int(res.rowcount)
