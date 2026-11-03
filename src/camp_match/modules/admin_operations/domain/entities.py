from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

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
from camp_match.shared_kernel.domain.identifiers import EntityId


class DomainError(Exception):
    pass


class InvalidIssueTransition(DomainError):
    pass


class InvalidIssue(DomainError):
    pass


class InvalidResolution(DomainError):
    pass


@dataclass(frozen=True)
class OperationalIssue:
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
    resolved_at: datetime | None = None
    resolution_summary: str | None = None

    def __post_init__(self) -> None:
        if not (1 <= len(self.title) <= 120):
            raise InvalidIssue("Title must be between 1 and 120 characters.")
        if not (1 <= len(self.description) <= 2000):
            raise InvalidIssue(
                "Description must be between 1 and 2000 characters."
            )
        if len(self.references) > 5:
            raise InvalidIssue("An issue can have at most 5 references.")
        if self.version < 1:
            raise InvalidIssue("Version must be at least 1.")

    def transition_to(
        self,
        new_status: IssueStatus,
        *,
        reason: str | None = None,
        resolution_summary: str | None = None,
        now: datetime,
    ) -> OperationalIssue:
        current = self.status
        allowed = False

        if (
            current == IssueStatus.OPEN
            and new_status == IssueStatus.IN_PROGRESS
        ):
            if self.assignee_id is None:
                raise InvalidIssueTransition(
                    "Assignee required to move to IN_PROGRESS."
                )
            allowed = True
        elif (
            current == IssueStatus.IN_PROGRESS
            and new_status == IssueStatus.AWAITING_INFORMATION
        ):
            if not reason or not reason.strip():
                raise InvalidIssueTransition(
                    "Reason required to move to AWAITING_INFORMATION."
                )
            allowed = True
        elif (
            current == IssueStatus.AWAITING_INFORMATION
            and new_status == IssueStatus.IN_PROGRESS
        ):
            allowed = True
        elif (
            current == IssueStatus.IN_PROGRESS
            and new_status == IssueStatus.RESOLVED
        ):
            summary = (
                resolution_summary or self.resolution_summary
            )
            if not summary or len(summary.strip()) < 10:
                raise InvalidResolution(
                    "Resolution summary of at least 10 chars required."
                )
            allowed = True
        elif (
            current == IssueStatus.RESOLVED
            and new_status == IssueStatus.CLOSED
        ):
            allowed = True
        elif (
            current == IssueStatus.RESOLVED
            and new_status == IssueStatus.IN_PROGRESS
        ):
            if not reason or not reason.strip():
                raise InvalidIssueTransition(
                    "Reason required to reopen resolved issue."
                )
            allowed = True

        if not allowed:
            raise InvalidIssueTransition(
                f"Invalid transition from {current} to {new_status}."
            )

        res_sum = (
            resolution_summary
            if new_status == IssueStatus.RESOLVED
            else self.resolution_summary
        )
        if new_status == IssueStatus.RESOLVED:
            res_at: datetime | None = now
        elif new_status == IssueStatus.CLOSED:
            res_at = None
        else:
            res_at = self.resolved_at

        return OperationalIssue(
            id=self.id,
            category=self.category,
            title=self.title,
            description=self.description,
            priority=self.priority,
            status=new_status,
            assignee_id=self.assignee_id,
            references=self.references,
            created_by=self.created_by,
            idempotency_key=self.idempotency_key,
            version=self.version + 1,
            created_at=self.created_at,
            updated_at=now,
            resolved_at=res_at,
            resolution_summary=res_sum,
        )

    def assign(
        self, assignee_id: EntityId | None, now: datetime
    ) -> OperationalIssue:
        valid_statuses = {
            IssueStatus.OPEN,
            IssueStatus.IN_PROGRESS,
            IssueStatus.AWAITING_INFORMATION,
        }
        if self.status not in valid_statuses:
            raise InvalidIssueTransition(
                f"Cannot assign issue in status {self.status}."
            )
        return OperationalIssue(
            id=self.id,
            category=self.category,
            title=self.title,
            description=self.description,
            priority=self.priority,
            status=self.status,
            assignee_id=assignee_id,
            references=self.references,
            created_by=self.created_by,
            idempotency_key=self.idempotency_key,
            version=self.version + 1,
            created_at=self.created_at,
            updated_at=now,
            resolved_at=self.resolved_at,
            resolution_summary=self.resolution_summary,
        )


@dataclass(frozen=True)
class IssueEvent:
    id: EntityId
    issue_id: EntityId
    event_type: str
    actor_id: EntityId
    occurred_at: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditEvent:
    id: EntityId
    action_id: EntityId
    event_type: AuditEventType
    action_type: AdminActionType
    actor_id: EntityId
    target_type: AuditTargetType
    target_id: EntityId | None = None
    reason: str | None = None
    outcome_code: str | None = None
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )
    request_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            self.event_type == AuditEventType.ACTION_REQUESTED
            and (
                not self.reason
                or not self.reason.strip()
                or len(self.reason.strip()) < 5
            )
        ):
            raise DomainError(
                "Reason required on ACTION_REQUESTED (min 5 chars)."
            )
        if (
            self.event_type
            in {AuditEventType.ACTION_SUCCEEDED, AuditEventType.ACTION_FAILED}
            and (not self.outcome_code or not self.outcome_code.strip())
        ):
            raise DomainError("Outcome code required on outcome audit events.")


@dataclass(frozen=True)
class OverviewSection:
    name: str
    status: SectionStatus
    as_of: datetime
    data: dict[str, Any] | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if self.status == SectionStatus.OK:
            if self.data is None:
                raise DomainError("OK section requires data.")
            if self.reason_code is not None:
                raise DomainError("OK section cannot have reason_code.")
        elif self.status == SectionStatus.UNAVAILABLE:
            if self.reason_code not in {"timeout", "source_error"}:
                raise DomainError(
                    "UNAVAILABLE requires reason_code ('timeout'|'source_error')."
                )
            if self.data is not None:
                raise DomainError("UNAVAILABLE section cannot have data.")
        elif self.status == SectionStatus.NOT_AUTHORIZED:
            if self.data is not None or self.reason_code is not None:
                raise DomainError(
                    "NOT_AUTHORIZED section cannot have data or reason_code."
                )
