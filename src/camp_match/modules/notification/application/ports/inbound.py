"""Notification inbound ports and DTOs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from camp_match.modules.notification.domain.value_objects import (
    InboxStatus,
    NotificationCategory,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class ProcessOutcome(StrEnum):
    PROCESSED = "PROCESSED"
    SKIPPED = "SKIPPED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class CreateOutcome(StrEnum):
    CREATED = "CREATED"
    COLLAPSED = "COLLAPSED"


@dataclass(frozen=True, slots=True)
class TargetView:
    type: str
    id: EntityId


@dataclass(frozen=True, slots=True)
class NotificationView:
    id: EntityId
    category: NotificationCategory
    type: str
    title: str
    body: str
    target: TargetView | None
    event_count: int
    is_read: bool
    read_at: datetime | None
    created_at: datetime
    latest_event_at: datetime


@dataclass(frozen=True, slots=True)
class UnreadCountResult:
    unread_count: int


@dataclass(frozen=True, slots=True)
class MarkAllReadResult:
    marked_read: int


@dataclass(frozen=True, slots=True)
class InboxRow:
    event_id: str
    event_type: str
    payload: dict[str, Any]
    attempts: int


@dataclass(frozen=True, slots=True)
class ListNotificationsRequest:
    actor_id: EntityId
    unread_only: bool | None = None
    category: NotificationCategory | None = None
    page_request: PageRequest = PageRequest(page=1, page_size=20)


@dataclass(frozen=True, slots=True)
class GetUnreadCountRequest:
    actor_id: EntityId


@dataclass(frozen=True, slots=True)
class MarkNotificationReadRequest:
    actor_id: EntityId
    notification_id: EntityId


@dataclass(frozen=True, slots=True)
class MarkAllReadRequest:
    actor_id: EntityId
    category: NotificationCategory | None = None


@dataclass(frozen=True, slots=True)
class ReceiveEventRequest:
    event_id: str
    event_type: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProcessInboxEventRequest:
    event_id: str


@dataclass(frozen=True, slots=True)
class ProcessPendingInboxRequest:
    limit: int = 100


@dataclass(frozen=True, slots=True)
class RequeueDeadEventsRequest:
    pass


@dataclass(frozen=True, slots=True)
class GetInboxStatsRequest:
    pass


@runtime_checkable
class ListNotifications(Protocol):
    async def execute(self, request: ListNotificationsRequest) -> Page[NotificationView]:
        ...


@runtime_checkable
class GetUnreadCount(Protocol):
    async def execute(self, request: GetUnreadCountRequest) -> UnreadCountResult:
        ...


@runtime_checkable
class MarkNotificationRead(Protocol):
    async def execute(self, request: MarkNotificationReadRequest) -> NotificationView:
        ...


@runtime_checkable
class MarkAllRead(Protocol):
    async def execute(self, request: MarkAllReadRequest) -> MarkAllReadResult:
        ...


@runtime_checkable
class ReceiveEvent(Protocol):
    async def execute(self, request: ReceiveEventRequest) -> bool:
        ...


@runtime_checkable
class ProcessInboxEvent(Protocol):
    async def execute(self, request: ProcessInboxEventRequest) -> ProcessOutcome:
        ...


@runtime_checkable
class ProcessPendingInbox(Protocol):
    async def execute(self, request: ProcessPendingInboxRequest) -> dict[ProcessOutcome, int]:
        ...


@runtime_checkable
class RequeueDeadEvents(Protocol):
    async def execute(self, request: RequeueDeadEventsRequest) -> int:
        ...


@runtime_checkable
class GetInboxStats(Protocol):
    async def execute(self, request: GetInboxStatsRequest) -> dict[InboxStatus, int]:
        ...
