from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from camp_match.platform.db.base import Base


class AdminIssueModel(Base):
    __tablename__ = "admin_issues"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    priority: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    references: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(nullable=False)
    idempotency_key: Mapped[str] = mapped_column(nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_summary: Mapped[str | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "created_by",
            "idempotency_key",
            name="uq_admin_issues_created_by_idempotency_key",
        ),
        CheckConstraint("version >= 1", name="ck_admin_issues_version_gte_1"),
        CheckConstraint(
            "status <> 'RESOLVED' OR resolution_summary IS NOT NULL",
            name="ck_admin_issues_resolved_summary",
        ),
        Index("ix_admin_issues_status_priority_created", "status", "priority", "created_at"),
        Index(
            "ix_admin_issues_assignee",
            "assignee_id",
            postgresql_where=(assignee_id.is_not(None)),
        ),
    )


class AdminIssueEventModel(Base):
    __tablename__ = "admin_issue_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_admin_issue_events_issue_occurred", "issue_id", "occurred_at", "id"),
    )


class AdminAuditEventModel(Base):
    __tablename__ = "admin_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    action_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(nullable=False)
    action_type: Mapped[str] = mapped_column(nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    target_type: Mapped[str] = mapped_column(nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(nullable=True)
    outcome_code: Mapped[str | None] = mapped_column(nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_id: Mapped[str | None] = mapped_column(nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("action_id", "event_type", name="uq_admin_audit_action_id_event_type"),
        CheckConstraint(
            "event_type <> 'ACTION_REQUESTED' OR reason IS NOT NULL",
            name="ck_admin_audit_requested_reason",
        ),
        Index("ix_admin_audit_occurred_id", occurred_at.desc(), id),
        Index("ix_admin_audit_actor_occurred", "actor_id", "occurred_at"),
        Index("ix_admin_audit_target", "target_type", "target_id"),
        Index(
            "ix_admin_audit_requested",
            "occurred_at",
            postgresql_where=(event_type == "ACTION_REQUESTED"),
        ),
    )
