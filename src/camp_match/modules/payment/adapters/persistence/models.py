from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from camp_match.platform.db.base import Base


class PaymentAttemptModel(Base):
    __tablename__ = "payment_attempts"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    booking_id: Mapped[UUID] = mapped_column(nullable=False)
    student_id: Mapped[UUID] = mapped_column(nullable=False)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String, nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("student_id", "idempotency_key", name="uq_payment_attempt_student_idempotency"),
        CheckConstraint("amount_kobo > 0", name="check_payment_attempt_amount_positive"),
        CheckConstraint(
            "status IN ('INITIATED', 'PENDING', 'SUCCEEDED', 'FAILED', 'EXPIRED', 'CANCELLED')",
            name="check_payment_attempt_status",
        ),
    )


class PaymentModel(Base):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    payment_attempt_id: Mapped[UUID] = mapped_column(ForeignKey("payment_attempts.id"), nullable=False, unique=True)
    booking_id: Mapped[UUID] = mapped_column(nullable=False)
    student_id: Mapped[UUID] = mapped_column(nullable=False)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    provider_reference: Mapped[str] = mapped_column(String, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("amount_kobo > 0", name="check_payment_amount_positive"),
    )


class FundDispositionModel(Base):
    __tablename__ = "fund_dispositions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id"), nullable=False, unique=True)
    held_amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("held_amount_kobo > 0", name="check_fund_disposition_held_positive"),
        CheckConstraint(
            "status IN ('HELD', 'DISPUTE_HOLD', 'PARTIALLY_RELEASED', 'RELEASED', 'PARTIALLY_REFUNDED', 'REFUNDED', 'RECONCILIATION_REQUIRED')",
            name="check_fund_disposition_status",
        ),
    )


class ReleaseOperationModel(Base):
    __tablename__ = "release_operations"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    fund_disposition_id: Mapped[UUID] = mapped_column(ForeignKey("fund_dispositions.id"), nullable=False)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    decision_id: Mapped[UUID] = mapped_column(nullable=False)
    provider_operation_reference: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    provider_operation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_fee_kobo: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        CheckConstraint("amount_kobo > 0", name="check_release_operation_amount_positive"),
        CheckConstraint(
            "status IN ('DECISION_RECORDED', 'PROVIDER_INITIATED', 'PROVIDER_PENDING', 'SUCCEEDED', 'FAILED', 'RECONCILIATION_REQUIRED')",
            name="check_release_operation_status",
        ),
    )


class RefundOperationModel(Base):
    __tablename__ = "refund_operations"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    fund_disposition_id: Mapped[UUID] = mapped_column(ForeignKey("fund_dispositions.id"), nullable=False)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    decision_id: Mapped[UUID] = mapped_column(nullable=False)
    provider_operation_reference: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    provider_operation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_fee_kobo: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    provider_status_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        CheckConstraint("amount_kobo > 0", name="check_refund_operation_amount_positive"),
        CheckConstraint(
            "status IN ('DECISION_RECORDED', 'PROVIDER_INITIATED', 'PROVIDER_PENDING', 'SUCCEEDED', 'FAILED', 'RECONCILIATION_REQUIRED')",
            name="check_refund_operation_status",
        ),
    )


class DisputeModel(Base):
    __tablename__ = "disputes"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    fund_disposition_id: Mapped[UUID] = mapped_column(ForeignKey("fund_dispositions.id"), nullable=False, index=True)
    raised_by: Mapped[UUID] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'RESOLVED_RELEASE', 'RESOLVED_REFUND', 'RESOLVED_PARTIAL')",
            name="check_dispute_status",
        ),
        Index(
            "ix_disputes_open_unique",
            "fund_disposition_id",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
        ),
    )


class ProviderWebhookEventModel(Base):
    __tablename__ = "provider_webhook_events"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String, nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    raw_payload_digest: Mapped[str] = mapped_column(String, nullable=False)
    normalized_event_type: Mapped[str] = mapped_column(String, nullable=False)
    correlated_attempt_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    processing_status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "processing_status IN ('RECEIVED', 'PROCESSED', 'IGNORED_DUPLICATE', 'FAILED_VALIDATION', 'UNCORRELATED')",
            name="check_webhook_processing_status",
        ),
    )


class ReleaseDecisionModel(Base):
    __tablename__ = "release_decisions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    fund_disposition_id: Mapped[UUID] = mapped_column(ForeignKey("fund_dispositions.id"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    policy_version: Mapped[str] = mapped_column(String, nullable=False)
    triggering_fact: Mapped[str] = mapped_column(String, nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    origin: Mapped[str] = mapped_column(String, nullable=False)
    authorized_by: Mapped[UUID | None] = mapped_column(nullable=True)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    student_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    warnings_sent_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    __table_args__ = (
        CheckConstraint("decision IN ('RELEASE', 'REFUND')", name="check_release_decision_type"),
        CheckConstraint("origin IN ('AUTOMATIC', 'MANUAL')", name="check_release_decision_origin"),
        CheckConstraint("amount_kobo > 0", name="check_release_decision_amount_positive"),
        CheckConstraint("decision <> 'RELEASE' OR student_confirmed_at IS NOT NULL", name="ck_release_requires_student_confirmation"),
        CheckConstraint("NOT (decision = 'RELEASE' AND origin = 'AUTOMATIC') OR warnings_sent_count >= 3", name="ck_auto_release_requires_three_warnings"),
    )


class ReleaseScheduleModel(Base):
    __tablename__ = "release_schedules"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    fund_disposition_id: Mapped[UUID] = mapped_column(ForeignKey("fund_dispositions.id"), nullable=False, unique=True, index=True)
    payment_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    booking_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    student_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cycle: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))
    window_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("cycle >= 1", name="check_release_schedule_cycle_positive"),
    )


class ReleaseWarningModel(Base):
    __tablename__ = "release_warnings"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    release_schedule_id: Mapped[UUID] = mapped_column(ForeignKey("release_schedules.id"), nullable=False, index=True)
    cycle: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    warning_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("release_schedule_id", "cycle", "warning_number", name="uq_release_warning_schedule_cycle_number"),
        CheckConstraint("cycle >= 1", name="check_release_warning_cycle_positive"),
        CheckConstraint("warning_number >= 1", name="check_release_warning_number_positive"),
        Index("ix_release_warnings_due_unsent", "due_at", postgresql_where=text("sent_at IS NULL AND superseded_at IS NULL")),
    )


class TransactionReviewModel(Base):
    __tablename__ = "transaction_reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id"), nullable=False, unique=True, index=True)
    fund_disposition_id: Mapped[UUID] = mapped_column(ForeignKey("fund_dispositions.id"), nullable=False, unique=True, index=True)
    payment_attempt_id: Mapped[UUID] = mapped_column(ForeignKey("payment_attempts.id"), nullable=False, index=True)
    booking_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    student_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    provider_id: Mapped[UUID | None] = mapped_column(nullable=True)
    property_id: Mapped[UUID | None] = mapped_column(nullable=True)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    provider_name: Mapped[str] = mapped_column(String, nullable=False)
    provider_reference: Mapped[str] = mapped_column(String, nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    booking_status: Mapped[str] = mapped_column(String, nullable=False)
    handover_offered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handover_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    student_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    release_cycle: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    release_window_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    warnings_required: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    warnings_sent: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    last_warning_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    open_dispute_id: Mapped[UUID | None] = mapped_column(nullable=True)
    dispute_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    released_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    refunded_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    stage: Mapped[str] = mapped_column(String, nullable=False, index=True)
    next_action: Mapped[str] = mapped_column(String, nullable=False)
    next_action_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))

    __table_args__ = (
        CheckConstraint("amount_kobo > 0", name="check_transaction_review_amount_positive"),
        CheckConstraint("released_kobo >= 0 AND refunded_kobo >= 0", name="check_transaction_review_ops_positive"),
        CheckConstraint("released_kobo + refunded_kobo <= amount_kobo", name="check_transaction_review_sum_lte_amount"),
        Index("ix_transaction_reviews_next_action", "next_action", postgresql_where=text("next_action <> 'NONE'")),
    )


class LedgerEntryModel(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    payment_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    fund_disposition_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    entry_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    reference_type: Mapped[str] = mapped_column(String, nullable=False)
    reference_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('CHARGE', 'HOLD_ALLOCATION', 'RELEASE', 'REFUND', 'REVERSAL', 'CORRECTION')",
            name="check_ledger_entry_type",
        ),
    )
