"""Notification API router."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from camp_match.modules.notification.adapters.api import dependencies
from camp_match.modules.notification.adapters.api.schemas import (
    NotificationResponse,
    PageSchema,
    ReadAllRequest,
    ReadAllResponse,
    TargetResponse,
    UnreadCountResponse,
)
from camp_match.modules.notification.application.ports.inbound import (
    GetUnreadCount,
    GetUnreadCountRequest,
    ListNotifications,
    ListNotificationsRequest,
    MarkAllRead,
    MarkAllReadRequest,
    MarkNotificationRead,
    MarkNotificationReadRequest,
    NotificationView,
)
from camp_match.modules.notification.domain.value_objects import NotificationCategory
from camp_match.platform.security.authentication import get_current_identity_id
from camp_match.shared_kernel.application.pagination import PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


def _to_response(v: NotificationView) -> NotificationResponse:
    target_resp = None
    if v.target:
        target_resp = TargetResponse(type=v.target.type, id=v.target.id.value)
    return NotificationResponse(
        id=v.id.value,
        category=v.category,
        type=v.type,
        title=v.title,
        body=v.body,
        target=target_resp,
        event_count=v.event_count,
        is_read=v.is_read,
        read_at=v.read_at,
        created_at=v.created_at,
        latest_event_at=v.latest_event_at,
    )


@router.get("", response_model=PageSchema[NotificationResponse])
async def list_notifications(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    list_uc: Annotated[
        ListNotifications,
        Depends(dependencies.get_list_notifications_use_case),
    ],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool | None = None,
    category: NotificationCategory | None = None,
) -> PageSchema[NotificationResponse]:
    page_req = PageRequest(page=page, page_size=page_size)
    page_result = await list_uc.execute(
        ListNotificationsRequest(
            actor_id=actor_id,
            unread_only=unread_only,
            category=category,
            page_request=page_req,
        )
    )
    items = [_to_response(item) for item in page_result.items]
    return PageSchema(
        items=items,
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    count_uc: Annotated[
        GetUnreadCount,
        Depends(dependencies.get_unread_count_use_case),
    ],
) -> UnreadCountResponse:
    res = await count_uc.execute(GetUnreadCountRequest(actor_id=actor_id))
    return UnreadCountResponse(unread_count=res.unread_count)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    mark_uc: Annotated[
        MarkNotificationRead,
        Depends(dependencies.get_mark_notification_read_use_case),
    ],
) -> NotificationResponse:
    view = await mark_uc.execute(
        MarkNotificationReadRequest(
            actor_id=actor_id,
            notification_id=EntityId(notification_id),
        )
    )
    return _to_response(view)


@router.post("/read-all", response_model=ReadAllResponse)
async def mark_all_read(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    mark_all_uc: Annotated[
        MarkAllRead,
        Depends(dependencies.get_mark_all_read_use_case),
    ],
    body: ReadAllRequest | None = None,
) -> ReadAllResponse:
    category = body.category if body else None
    res = await mark_all_uc.execute(
        MarkAllReadRequest(
            actor_id=actor_id,
            category=category,
        )
    )
    return ReadAllResponse(marked_read=res.marked_read)
