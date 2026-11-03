"""Notification API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from camp_match.modules.notification.domain.value_objects import NotificationCategory

T = TypeVar("T")


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TargetResponse(BaseSchema):
    type: str
    id: UUID


class NotificationResponse(BaseSchema):
    id: UUID
    category: NotificationCategory
    type: str
    title: str
    body: str
    target: TargetResponse | None
    event_count: int
    is_read: bool
    read_at: datetime | None
    created_at: datetime
    latest_event_at: datetime


class PageSchema[T](BaseSchema):
    items: list[T]
    total: int
    page: int
    page_size: int


class UnreadCountResponse(BaseSchema):
    unread_count: int


class ReadAllRequest(BaseSchema):
    category: NotificationCategory | None = None


class ReadAllResponse(BaseSchema):
    marked_read: int
