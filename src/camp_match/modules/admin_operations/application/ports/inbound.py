from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from camp_match.modules.admin_operations.domain.value_objects import (
    AdminActionType,
    AuditEventType,
    AuditTargetType,
    IssueCategory,
    IssuePriority,
    IssueStatus,
    ReferenceType,
    SectionStatus,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True)
class IssueView:
    id: EntityId
    category: IssueCategory
    title: str
    description: str
    priority: IssuePriority
    status: IssueStatus
    assignee_id: EntityId | None
    references: tuple[tuple[ReferenceType, EntityId], ...]
    created_by: EntityId
    idempotency_key: str
    version: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    resolution_summary: str | None


@dataclass(frozen=True)
class IssueDetailView:
    issue: IssueView
    history: list[IssueEventView]


@dataclass(frozen=True)
class IssueEventView:
    id: EntityId
    issue_id: EntityId
    event_type: str
    actor_id: EntityId
    occurred_at: datetime
    details: dict[str, Any]


@dataclass(frozen=True)
class AccountView:
    identity_id: EntityId
    status: str
    created_at: datetime
    roles: frozenset[str]


@dataclass(frozen=True)
class StaffView:
    identity_id: EntityId
    roles: frozenset[str]


@dataclass(frozen=True)
class AuditEventView:
    id: EntityId
    action_id: EntityId
    event_type: AuditEventType
    action_type: AdminActionType
    actor_id: EntityId
    target_type: AuditTargetType
    target_id: EntityId | None
    reason: str | None
    outcome_code: str | None
    occurred_at: datetime
    request_id: str | None
    details: dict[str, Any]


@dataclass(frozen=True)
class OverviewSectionView:
    name: str
    status: SectionStatus
    as_of: datetime
    data: dict[str, Any] | None = None
    reason_code: str | None = None


@dataclass(frozen=True)
class OverviewView:
    verification: OverviewSectionView
    payments: OverviewSectionView
    safety: OverviewSectionView
    notifications: OverviewSectionView


@dataclass(frozen=True)
class TaskView:
    task_id: str
    type: str
    priority: str
    since: datetime
    subject: dict[str, Any]
    target: dict[str, Any]
    facts: dict[str, Any]
    required_permission: str
    can_act: bool
    due_at: datetime | None = None


@dataclass(frozen=True)
class TaskSectionView:
    source: str
    status: str
    as_of: datetime
    items: list[TaskView]
    total: int | None = None
    reason_code: str | None = None


@dataclass(frozen=True)
class TasksView:
    as_of: datetime
    sections: list[TaskSectionView]


@dataclass(frozen=True)
class GetTasksRequest:
    actor_id: EntityId
    sources: list[str] | None = None
    types: list[str] | None = None
    priority: str | None = None
    limit_per_source: int | None = None


class GetTasks(Protocol):
    async def execute(self, request: GetTasksRequest) -> TasksView:
        ...
    messaging: OverviewSectionView
    issues: OverviewSectionView
    admin_actions: OverviewSectionView
    background_jobs: OverviewSectionView
    platform_events: OverviewSectionView


@dataclass(frozen=True)
class RoleGrantRequestView:
    id: EntityId
    target_identity_id: EntityId
    role: str
    requested_by: EntityId
    reason: str
    status: str
    decided_by: EntityId | None
    decided_at: datetime | None
    decision_reason: str | None
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class RecoveryResult:
    action_id: EntityId
    requeued: int


class GetOverview(Protocol):
    async def execute(self, actor_id: EntityId) -> OverviewView:
        ...


class CreateIssue(Protocol):
    async def execute(
        self,
        actor_id: EntityId,
        category: IssueCategory,
        title: str,
        description: str,
        priority: IssuePriority,
        references: tuple[tuple[ReferenceType, EntityId], ...],
        idempotency_key: str,
    ) -> IssueView:
        ...


class ListIssues(Protocol):
    async def execute(
        self,
        actor_id: EntityId,
        status: IssueStatus | None = None,
        assignee_id: EntityId | None = None,
        priority: IssuePriority | None = None,
        category: IssueCategory | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[IssueView]:
        ...


class GetIssue(Protocol):
    async def execute(
        self, actor_id: EntityId, issue_id: EntityId
    ) -> IssueView:
        ...


class AssignIssue(Protocol):
    async def execute(
        self,
        actor_id: EntityId,
        issue_id: EntityId,
        assignee_id: EntityId | None,
        version: int,
    ) -> IssueView:
        ...


class ChangeIssueStatus(Protocol):
    async def execute(
        self,
        actor_id: EntityId,
        issue_id: EntityId,
        new_status: IssueStatus,
        version: int,
        reason: str | None = None,
        resolution_summary: str | None = None,
    ) -> IssueView:
        ...


class GetAccount(Protocol):
    async def execute(
        self, actor_id: EntityId, identity_id: EntityId
    ) -> AccountView:
        ...


class DisableAccount(Protocol):
    async def execute(
        self, actor_id: EntityId, identity_id: EntityId, reason: str
    ) -> AccountView:
        ...


class ReactivateAccount(Protocol):
    async def execute(
        self, actor_id: EntityId, identity_id: EntityId, reason: str
    ) -> AccountView:
        ...


class ListStaff(Protocol):
    async def execute(
        self,
        actor_id: EntityId,
        role: str,
        page_request: PageRequest | None = None,
    ) -> Page[StaffView]:
        ...


class GrantStaffRole(Protocol):
    async def execute(
        self,
        actor_id: EntityId,
        identity_id: EntityId,
        role: str,
        reason: str,
    ) -> StaffView:
        ...


class RevokeStaffRole(Protocol):
    async def execute(
        self,
        actor_id: EntityId,
        identity_id: EntityId,
        role: str,
        reason: str,
    ) -> StaffView:
        ...


class RequeueDeadNotificationEvents(Protocol):
    async def execute(
        self, actor_id: EntityId, reason: str
    ) -> RecoveryResult:
        ...


class RequeueFailedSafetyEnforcement(Protocol):
    async def execute(
        self, actor_id: EntityId, reason: str
    ) -> RecoveryResult:
        ...


class ListAuditEvents(Protocol):
    async def execute(
        self,
        actor_id: EntityId,
        actor_filter_id: EntityId | None = None,
        action_type: AdminActionType | None = None,
        target_id: EntityId | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page_request: PageRequest | None = None,
    ) -> Page[AuditEventView]:
        ...
