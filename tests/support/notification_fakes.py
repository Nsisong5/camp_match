"""Notification fakes for unit and integration testing."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from camp_match.modules.notification.application.ports.inbound import CreateOutcome, InboxRow
from camp_match.modules.notification.domain.entities import Notification
from camp_match.modules.notification.domain.value_objects import InboxStatus, NotificationCategory
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class InMemoryNotificationRepository:
    def __init__(self) -> None:
        self.notifications: dict[EntityId, Notification] = {}

    async def create_or_collapse(self, notification: Notification) -> CreateOutcome:
        if notification.group_key:
            for notif in self.notifications.values():
                if (
                    notif.recipient_id == notification.recipient_id
                    and notif.group_key == notification.group_key
                    and not notif.is_read
                ):
                    notif.event_count += 1
                    if notification.latest_event_at > notif.latest_event_at:
                        notif.latest_event_at = notification.latest_event_at
                    return CreateOutcome.COLLAPSED

        self.notifications[notification.id] = notification
        return CreateOutcome.CREATED

    async def list_for_recipient(
        self,
        recipient_id: EntityId,
        unread_only: bool | None,
        category: NotificationCategory | None,
        page_request: PageRequest,
    ) -> Page[Notification]:
        items = [
            n for n in self.notifications.values()
            if n.recipient_id == recipient_id
        ]
        if unread_only:
            items = [n for n in items if not n.is_read]
        if category:
            items = [n for n in items if n.category == category]

        items.sort(key=lambda n: (n.latest_event_at, n.id.value), reverse=True)
        total = len(items)
        start = (page_request.page - 1) * page_request.page_size
        end = start + page_request.page_size
        page_items = items[start:end]

        return Page(
            items=page_items,
            total=total,
            page=page_request.page,
            page_size=page_request.page_size,
        )

    async def count_unread(self, recipient_id: EntityId) -> int:
        return sum(
            1 for n in self.notifications.values()
            if n.recipient_id == recipient_id and not n.is_read
        )

    async def get_by_id(
        self, notification_id: EntityId, recipient_id: EntityId
    ) -> Notification | None:
        n = self.notifications.get(notification_id)
        if n and n.recipient_id == recipient_id:
            return n
        return None

    async def mark_read(
        self, notification_id: EntityId, recipient_id: EntityId, now: datetime
    ) -> bool:
        n = self.notifications.get(notification_id)
        if not n or n.recipient_id != recipient_id:
            return False
        return n.mark_read(now)

    async def exists_for_recipient(
        self, notification_id: EntityId, recipient_id: EntityId
    ) -> bool:
        n = self.notifications.get(notification_id)
        return n is not None and n.recipient_id == recipient_id

    async def mark_all_read(
        self,
        recipient_id: EntityId,
        category: NotificationCategory | None,
        now: datetime,
    ) -> int:
        count = 0
        for n in self.notifications.values():
            if n.recipient_id == recipient_id and not n.is_read:
                if category is None or n.category == category:
                    if n.mark_read(now):
                        count += 1
        return count


class InMemoryInboxRepository:
    def __init__(self) -> None:
        self.events: dict[str, dict[str, Any]] = {}

    async def add(
        self, event_id: str, event_type: str, payload: dict[str, Any], now: datetime
    ) -> bool:
        if event_id in self.events:
            return False
        self.events[event_id] = {
            "event_type": event_type,
            "payload": payload,
            "status": "PENDING",
            "attempts": 0,
            "next_attempt_at": now,
        }
        return True

    async def claim(self, event_id: str) -> InboxRow | None:
        ev = self.events.get(event_id)
        if not ev or ev["status"] != "PENDING":
            return None
        ev["status"] = "CLAIMED"
        return InboxRow(
            event_id=event_id,
            event_type=ev["event_type"],
            payload=ev["payload"],
            attempts=ev["attempts"],
        )

    async def mark_processed(self, event_id: str, now: datetime) -> None:
        if event_id in self.events:
            self.events[event_id]["status"] = "PROCESSED"

    async def mark_rejected(self, event_id: str, code: str, now: datetime) -> None:
        if event_id in self.events:
            self.events[event_id]["status"] = "REJECTED"
            self.events[event_id]["last_error"] = code

    async def record_failure(
        self,
        event_id: str,
        error_class: str,
        next_attempt_at: datetime,
        dead: bool,
    ) -> None:
        ev = self.events.get(event_id)
        if ev:
            ev["attempts"] += 1
            ev["last_error"] = error_class
            ev["next_attempt_at"] = next_attempt_at
            ev["status"] = "DEAD" if dead else "PENDING"

    async def list_due(self, now: datetime, limit: int) -> list[str]:
        due = []
        for eid, ev in self.events.items():
            if ev["status"] == "PENDING" and ev["next_attempt_at"] <= now:
                due.append(eid)
        return due[:limit]

    async def requeue_dead(self) -> int:
        count = 0
        for ev in self.events.values():
            if ev["status"] == "DEAD":
                ev["status"] = "PENDING"
                ev["attempts"] = 0
                count += 1
        return count

    async def stats(self) -> dict[InboxStatus, int]:
        counts = {st: 0 for st in InboxStatus}
        for ev in self.events.values():
            st = InboxStatus(ev["status"])
            counts[st] += 1
        return counts


class InMemoryPropertyOwnerProvider:
    def __init__(self, owners: dict[EntityId, EntityId] | None = None) -> None:
        self.owners = owners or {}

    async def get_owner(self, property_id: EntityId) -> EntityId | None:
        return self.owners.get(property_id)
