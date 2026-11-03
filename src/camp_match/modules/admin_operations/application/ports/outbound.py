from __future__ import annotations

import builtins
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from camp_match.modules.admin_operations.domain.entities import (
    AuditEvent,
    IssueEvent,
    OperationalIssue,
)
from camp_match.modules.admin_operations.domain.value_objects import (
    AdminActionType,
    IssueCategory,
    IssuePriority,
    IssueStatus,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True)
class AccountInfo:
    identity_id: EntityId
    status: str
    created_at: datetime


class IssueRepository(Protocol):
    async def add(self, issue: OperationalIssue) -> None:
        ...

    async def get(self, issue_id: EntityId) -> OperationalIssue | None:
        ...

    async def list(
        self,
        status: IssueStatus | None = None,
        assignee_id: EntityId | None = None,
        priority: IssuePriority | None = None,
        category: IssueCategory | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[OperationalIssue]:
        ...

    async def update_status(
        self,
        issue_id: EntityId,
        new_status: IssueStatus,
        expected_version: int,
        now: datetime,
        resolution_summary: str | None = None,
    ) -> bool:
        ...

    async def update_assignee(
        self,
        issue_id: EntityId,
        assignee_id: EntityId | None,
        expected_version: int,
        now: datetime,
    ) -> bool:
        ...

    async def add_event(self, event: IssueEvent) -> None:
        ...

    async def list_events(self, issue_id: EntityId) -> builtins.list[IssueEvent]:
        ...

    async def counts_by_status(self) -> dict[str, int]:
        ...

    async def count_unassigned_open(self) -> int:
        ...

    async def count_high_priority_open(self) -> int:
        ...


class AuditRepository(Protocol):
    async def add(self, event: AuditEvent) -> None:
        ...

    async def list(
        self,
        actor_id: EntityId | None = None,
        action_type: AdminActionType | None = None,
        target_id: EntityId | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[AuditEvent]:
        ...

    async def count_uncertain(self, cutoff: datetime) -> tuple[int, datetime | None]:
        ...


class AccountProvider(Protocol):
    async def get(self, identity_id: EntityId) -> AccountInfo | None:
        ...

    async def disable(self, identity_id: EntityId, reason: str) -> None:
        ...

    async def reactivate(self, identity_id: EntityId, reason: str) -> None:
        ...


class StaffRoleProvider(Protocol):
    async def assign(self, actor_id: EntityId, identity_id: EntityId, role: str) -> None:
        ...

    async def revoke(self, actor_id: EntityId, identity_id: EntityId, role: str) -> None:
        ...

    async def list(
        self, actor_id: EntityId, role: str, page_request: PageRequest | None = None
    ) -> Page[tuple[EntityId, frozenset[str]]]:
        ...

    async def get_roles(self, identity_id: EntityId) -> frozenset[str]:
        ...


class Authorizer(Protocol):
    async def authorize(self, identity_id: EntityId, permission: Any) -> bool:
        ...


class VerificationSource(Protocol):
    async def fetch(self, actor_id: EntityId) -> dict[str, Any]:
        ...


class PaymentSource(Protocol):
    async def fetch(self, actor_id: EntityId) -> dict[str, Any]:
        ...


class SafetySource(Protocol):
    async def fetch(self, actor_id: EntityId) -> dict[str, Any]:
        ...


class NotificationSource(Protocol):
    async def fetch(self) -> dict[str, Any]:
        ...


class MessagingSource(Protocol):
    async def fetch(self) -> dict[str, Any]:
        ...


class NotificationRecovery(Protocol):
    async def requeue_dead(self) -> int:
        ...


class SafetyRecovery(Protocol):
    async def requeue_failed(self) -> int:
        ...
