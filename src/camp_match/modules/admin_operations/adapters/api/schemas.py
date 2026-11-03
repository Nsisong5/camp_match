from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_serializer

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


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def coerce_entity_ids(cls, v: Any) -> Any:
        if hasattr(v, "value") and isinstance(v.value, UUID):
            return v.value
        return v

    @model_serializer(mode="wrap")
    def serialize_model(self, handler: Any) -> Any:
        res = handler(self)
        def _coerce(obj: Any) -> Any:
            if hasattr(obj, "value") and isinstance(obj.value, UUID):
                return obj.value
            if isinstance(obj, dict):
                return {k: _coerce(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_coerce(v) for v in obj]
            if isinstance(obj, tuple):
                return tuple(_coerce(v) for v in obj)
            return obj
        return _coerce(res)


class IssueViewSchema(BaseSchema):
    id: UUID
    category: IssueCategory
    title: str
    description: str
    priority: IssuePriority
    status: IssueStatus
    assignee_id: UUID | None
    references: list[tuple[ReferenceType, UUID]]
    created_by: UUID
    idempotency_key: str
    version: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    resolution_summary: str | None


class IssueEventViewSchema(BaseSchema):
    id: UUID
    issue_id: UUID
    event_type: str
    actor_id: UUID
    occurred_at: datetime
    details: dict[str, Any]


class IssueDetailViewSchema(BaseSchema):
    issue: IssueViewSchema
    history: list[IssueEventViewSchema]


class AccountViewSchema(BaseSchema):
    identity_id: UUID
    status: str
    created_at: datetime
    roles: list[str]


class StaffViewSchema(BaseSchema):
    identity_id: UUID
    roles: list[str]


class PageSchema[T](BaseSchema):
    items: list[T]
    total: int
    page: int
    page_size: int


class AuditEventViewSchema(BaseSchema):
    id: UUID
    action_id: UUID
    event_type: AuditEventType
    action_type: AdminActionType
    actor_id: UUID
    target_type: AuditTargetType
    target_id: UUID | None
    reason: str | None
    outcome_code: str | None
    occurred_at: datetime
    request_id: str | None
    details: dict[str, Any]


class OverviewSectionViewSchema(BaseSchema):
    name: str
    status: SectionStatus
    as_of: datetime
    data: dict[str, Any] | None = None
    reason_code: str | None = None


class OverviewViewSchema(BaseSchema):
    verification: OverviewSectionViewSchema
    payments: OverviewSectionViewSchema
    safety: OverviewSectionViewSchema
    notifications: OverviewSectionViewSchema
    messaging: OverviewSectionViewSchema
    issues: OverviewSectionViewSchema
    admin_actions: OverviewSectionViewSchema


class RecoveryResultSchema(BaseSchema):
    action_id: UUID
    requeued: int


class CreateIssueSchema(BaseSchema):
    category: IssueCategory
    title: str
    description: str
    priority: IssuePriority = IssuePriority.NORMAL
    references: list[tuple[ReferenceType, UUID]] = []
    idempotency_key: str


class AssignIssueSchema(BaseSchema):
    assignee_id: UUID | None
    version: int


class ResolveIssueSchema(BaseSchema):
    resolution_summary: str
    version: int


class ChangeStatusSchema(BaseSchema):
    to_status: IssueStatus
    version: int
    reason: str | None = None
    resolution_summary: str | None = None


class ReasonSchema(BaseSchema):
    reason: str


class GrantRoleSchema(BaseSchema):
    role: str
    reason: str
