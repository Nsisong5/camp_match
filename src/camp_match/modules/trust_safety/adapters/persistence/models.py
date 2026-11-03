"""Trust & Safety SQLAlchemy persistence models."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from camp_match.platform.db.base import Base


class SafetyReportModel(Base):
    __tablename__ = "safety_reports"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    reporter_id: Mapped[UUID] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    subject_id: Mapped[UUID] = mapped_column(nullable=False)
    subject_user_id: Mapped[UUID] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("reporter_id", "idempotency_key", name="uq_safety_reporter_idempotency"),
        Index(
            "uq_safety_duplicate_open_report",
            "reporter_id",
            "subject_type",
            "subject_id",
            "category",
            unique=True,
            postgresql_where=text("status <> 'CLOSED'"),
        ),
        Index("ix_safety_reports_reporter_created", "reporter_id", text("created_at DESC")),
        Index("ix_safety_reports_queue", "status", "created_at"),
        CheckConstraint("reporter_id <> subject_user_id", name="check_safety_report_reporter_not_subject"),
    )


class SafetyCaseModel(Base):
    __tablename__ = "safety_cases"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    subject_user_id: Mapped[UUID] = mapped_column(nullable=False)
    assigned_to: Mapped[UUID | None] = mapped_column(nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_safety_cases_queue", "status", "priority", "created_at"),
        Index(
            "ix_safety_cases_assigned",
            "assigned_to",
            postgresql_where=text("assigned_to IS NOT NULL"),
        ),
        CheckConstraint("version >= 1", name="check_safety_case_version"),
        CheckConstraint("cycle >= 1", name="check_safety_case_cycle"),
    )


class SafetyCaseReportModel(Base):
    __tablename__ = "safety_case_reports"

    report_id: Mapped[UUID] = mapped_column(primary_key=True)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("safety_cases.id", ondelete="CASCADE"), nullable=False)
    linked_by: Mapped[UUID] = mapped_column(nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_safety_case_reports_case_id", "case_id"),
    )


class SafetyEvidenceModel(Base):
    __tablename__ = "safety_evidence"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    report_id: Mapped[UUID] = mapped_column(ForeignKey("safety_reports.id", ondelete="CASCADE"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[UUID] = mapped_column(nullable=False)
    conversation_id: Mapped[UUID | None] = mapped_column(nullable=True)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    collected_by: Mapped[UUID] = mapped_column(nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    confidentiality: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_safety_evidence_report_id", "report_id"),
        CheckConstraint(
            "(evidence_type <> 'MESSAGE_SNAPSHOT') OR "
            "(snapshot IS NOT NULL AND content_sha256 IS NOT NULL AND confidentiality = 'RESTRICTED')",
            name="check_safety_evidence_snapshot",
        ),
    )


class SafetyNoteModel(Base):
    __tablename__ = "safety_notes"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("safety_cases.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[UUID] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    cited_evidence_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    corrects_note_id: Mapped[UUID | None] = mapped_column(ForeignKey("safety_notes.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_safety_notes_case_created", "case_id", "created_at"),
        CheckConstraint(
            "(kind <> 'CORROBORATED_FACT') OR (jsonb_array_length(cited_evidence_ids) > 0)",
            name="check_safety_note_corroborated_fact",
        ),
    )


class SafetyDecisionModel(Base):
    __tablename__ = "safety_decisions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("safety_cases.id", ondelete="CASCADE"), nullable=False)
    cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_type: Mapped[str] = mapped_column(String, nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    cited_evidence_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    cited_note_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    decided_by: Mapped[UUID] = mapped_column(nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_safety_decisions_case_decided", "case_id", "decided_at"),
        Index(
            "uq_safety_case_cycle_final_decision",
            "case_id",
            "cycle",
            unique=True,
            postgresql_where=text("is_final = true"),
        ),
    )


class SafetyEnforcementActionModel(Base):
    __tablename__ = "safety_enforcement_actions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("safety_cases.id", ondelete="CASCADE"), nullable=False)
    decision_id: Mapped[UUID] = mapped_column(ForeignKey("safety_decisions.id", ondelete="CASCADE"), nullable=False)
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    target_user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_listing_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_key: Mapped[str] = mapped_column(String, nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_by: Mapped[UUID] = mapped_column(nullable=False)
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_by: Mapped[UUID | None] = mapped_column(nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by: Mapped[UUID | None] = mapped_column(nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_safety_live_enforcement_action",
            "case_id",
            "action_type",
            "target_key",
            unique=True,
            postgresql_where=text("status IN ('PROPOSED', 'APPROVED', 'APPLIED', 'REVERSAL_PENDING')"),
        ),
        Index(
            "ix_safety_enforcement_due",
            "next_attempt_at",
            postgresql_where=text("status IN ('APPROVED', 'REVERSAL_PENDING')"),
        ),
        CheckConstraint("attempts >= 0", name="check_safety_enforcement_attempts"),
        CheckConstraint(
            "(action_type = 'LISTING_SUSPENSION' AND target_listing_id IS NOT NULL AND target_user_id IS NULL) OR "
            "(action_type <> 'LISTING_SUSPENSION' AND target_user_id IS NOT NULL AND target_listing_id IS NULL)",
            name="check_safety_enforcement_targets",
        ),
    )


class SafetyCaseEventModel(Base):
    __tablename__ = "safety_case_events"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    case_id: Mapped[UUID | None] = mapped_column(ForeignKey("safety_cases.id", ondelete="CASCADE"), nullable=True)
    report_id: Mapped[UUID | None] = mapped_column(ForeignKey("safety_reports.id", ondelete="CASCADE"), nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_safety_case_events_case_occurred", "case_id", "occurred_at", "id"),
        CheckConstraint("case_id IS NOT NULL OR report_id IS NOT NULL", name="check_safety_event_target"),
    )
