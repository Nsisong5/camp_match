"""Notification entity."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from camp_match.modules.notification.domain.value_objects import (
    NotificationCategory,
    NotificationTarget,
    NotificationType,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass
class Notification:
    id: EntityId
    recipient_id: EntityId
    type: NotificationType
    category: NotificationCategory
    title: str
    body: str
    target: NotificationTarget | None = None
    group_key: str | None = None
    event_count: int = 1
    source_event_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    latest_event_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    read_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.category != self.type.category:
            raise ValueError(
                f"Category {self.category} does not match type "
                f"category {self.type.category}."
            )
        if self.group_key is not None and not self.type.is_collapsible:
            raise ValueError(
                f"Notification type {self.type.value} is not collapsible "
                "but group_key was provided."
            )
        if self.event_count < 1:
            raise ValueError("event_count must be at least 1.")

        if not self.title or not self.title.strip():
            raise ValueError("Title cannot be empty.")
        if len(self.title) > 100:
            raise ValueError("Title exceeds maximum length of 100 characters.")

        if not self.body or not self.body.strip():
            raise ValueError("Body cannot be empty.")
        if len(self.body) > 300:
            raise ValueError("Body exceeds maximum length of 300 characters.")

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def mark_read(self, now: datetime | None = None) -> bool:
        if self.read_at is not None:
            return False
        self.read_at = now or datetime.now(UTC)
        return True
