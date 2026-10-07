from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    Boolean,
    DateTime,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from camp_match.platform.db.base import Base


class VerificationCaseModel(Base):
    __tablename__ = "verification_cases"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    previous_case_id: Mapped[UUID | None] = mapped_column(ForeignKey("verification_cases.id"), nullable=True)
    submitted_by: Mapped[UUID] = mapped_column(nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[UUID | None] = mapped_column(nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("target_type IN ('PROVIDER', 'PROPERTY')", name="check_verification_target_type"),
        Index(
            "uq_in_flight_verification_case",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where=(
                "status IN ('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'INSPECTION_REQUIRED', 'INSPECTION_IN_PROGRESS', 'INSPECTION_COMPLETED', 'DECISION_PENDING')"
            ),
        ),
    )


class VerificationEvidenceModel(Base):
    __tablename__ = "verification_evidence"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    verification_case_id: Mapped[UUID] = mapped_column(ForeignKey("verification_cases.id", ondelete="CASCADE"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String, nullable=False)
    media_id: Mapped[UUID] = mapped_column(nullable=False)
    submitted_by: Mapped[UUID] = mapped_column(nullable=False)
    source_description: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inspection_id: Mapped[UUID | None] = mapped_column(ForeignKey("inspections.id", ondelete="SET NULL"), nullable=True)
    review_status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    review_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InspectionModel(Base):
    __tablename__ = "inspections"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    verification_case_id: Mapped[UUID] = mapped_column(ForeignKey("verification_cases.id", ondelete="CASCADE"), nullable=False)
    inspector_id: Mapped[UUID] = mapped_column(nullable=False)
    assigned_by: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ASSIGNED")
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)


class InspectionObservationModel(Base):
    __tablename__ = "inspection_observations"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    inspection_id: Mapped[UUID] = mapped_column(ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False)
    item: Mapped[str] = mapped_column(String, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("inspection_id", "item", name="uq_inspection_observation_item"),
    )


class VerificationDecisionModel(Base):
    __tablename__ = "verification_decisions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    verification_case_id: Mapped[UUID] = mapped_column(ForeignKey("verification_cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    decided_by: Mapped[UUID] = mapped_column(nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VerificationHistoryModel(Base):
    __tablename__ = "verification_history"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    verification_case_id: Mapped[UUID] = mapped_column(ForeignKey("verification_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    details: Mapped[str | None] = mapped_column(String, nullable=True)
