"""List notifications use case."""
from __future__ import annotations

from camp_match.modules.notification.application.ports.inbound import (
    ListNotificationsRequest,
    NotificationView,
    TargetView,
)
from camp_match.modules.notification.application.ports.outbound import (
    NotificationRepository,
)
from camp_match.shared_kernel.application.pagination import Page


class ListNotificationsUseCase:
    def __init__(self, notification_repo: NotificationRepository) -> None:
        self.notification_repo = notification_repo

    async def execute(self, request: ListNotificationsRequest) -> Page[NotificationView]:
        page = await self.notification_repo.list_for_recipient(
            recipient_id=request.actor_id,
            unread_only=request.unread_only,
            category=request.category,
            page_request=request.page_request,
        )

        views = []
        for n in page.items:
            target_view = None
            if n.target:
                target_view = TargetView(type=n.target.type.value, id=n.target.id)
            views.append(
                NotificationView(
                    id=n.id,
                    category=n.category,
                    type=n.type.value,
                    title=n.title,
                    body=n.body,
                    target=target_view,
                    event_count=n.event_count,
                    is_read=n.is_read,
                    read_at=n.read_at,
                    created_at=n.created_at,
                    latest_event_at=n.latest_event_at,
                )
            )

        return Page(
            items=views,
            total=page.total,
            page=page.page,
            page_size=page.page_size,
        )
