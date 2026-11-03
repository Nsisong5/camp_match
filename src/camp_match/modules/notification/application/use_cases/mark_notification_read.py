"""Mark notification read use case."""
from __future__ import annotations

from camp_match.modules.notification.application.errors import NotificationNotFound
from camp_match.modules.notification.application.ports.inbound import (
    MarkNotificationReadRequest,
    NotificationView,
    TargetView,
)
from camp_match.modules.notification.application.ports.outbound import (
    NotificationRepository,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock


class MarkNotificationReadUseCase:
    def __init__(
        self,
        notification_repo: NotificationRepository,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.notification_repo = notification_repo
        self.uow = uow
        self.clock = clock

    async def execute(self, request: MarkNotificationReadRequest) -> NotificationView:
        now = self.clock.now()
        async with self.uow:
            await self.notification_repo.mark_read(
                request.notification_id, request.actor_id, now
            )
            await self.uow.commit()

        notif = await self.notification_repo.get_by_id(
            request.notification_id, request.actor_id
        )
        if not notif:
            exists = await self.notification_repo.exists_for_recipient(
                request.notification_id, request.actor_id
            )
            if not exists:
                raise NotificationNotFound("Notification not found.")
            raise NotificationNotFound("Notification not found.")

        target_view = None
        if notif.target:
            target_view = TargetView(type=notif.target.type.value, id=notif.target.id)
        return NotificationView(
            id=notif.id,
            category=notif.category,
            type=notif.type.value,
            title=notif.title,
            body=notif.body,
            target=target_view,
            event_count=notif.event_count,
            is_read=notif.is_read,
            read_at=notif.read_at,
            created_at=notif.created_at,
            latest_event_at=notif.latest_event_at,
        )
