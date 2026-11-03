"""Notification outbound ports."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from camp_match.modules.notification.application.ports.inbound import (
    CreateOutcome,
    InboxRow,
)
from camp_match.modules.notification.domain.entities import Notification
from camp_match.modules.notification.domain.value_objects import (
    InboxStatus,
    NotificationCategory,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


@runtime_checkable
class NotificationRepository(Protocol):
    async def create_or_collapse(self, notification: Notification) -> CreateOutcome:
        ...

    async def list_for_recipient(
        self,
        recipient_id: EntityId,
        unread_only: bool | None,
        category: NotificationCategory | None,
        page_request: PageRequest,
    ) -> Page[Notification]:
        ...

    async def count_unread(self, recipient_id: EntityId) -> int:
        ...

    async def get_by_id(
        self, notification_id: EntityId, recipient_id: EntityId
    ) -> Notification | None:
        ...

    async def mark_read(
        self, notification_id: EntityId, recipient_id: EntityId, now: datetime
    ) -> bool:
        ...

    async def exists_for_recipient(
        self, notification_id: EntityId, recipient_id: EntityId
    ) -> bool:
        ...

    async def mark_all_read(
        self,
        recipient_id: EntityId,
        category: NotificationCategory | None,
        now: datetime,
    ) -> int:
        ...


@runtime_checkable
class InboxRepository(Protocol):
    async def add(
        self, event_id: str, event_type: str, payload: dict[str, Any], now: datetime
    ) -> bool:
        ...

    async def claim(self, event_id: str) -> InboxRow | None:
        ...

    async def mark_processed(self, event_id: str, now: datetime) -> None:
        ...

    async def mark_rejected(self, event_id: str, code: str, now: datetime) -> None:
        ...

    async def record_failure(
        self,
        event_id: str,
        error_class: str,
        next_attempt_at: datetime,
        dead: bool,
    ) -> None:
        ...

    async def list_due(self, now: datetime, limit: int) -> list[str]:
        ...

    async def requeue_dead(self) -> int:
        ...

    async def stats(self) -> dict[InboxStatus, int]:
        ...


@runtime_checkable
class PropertyOwnerProvider(Protocol):
    async def get_owner(self, property_id: EntityId) -> EntityId | None:
        ...
