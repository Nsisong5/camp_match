from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from camp_match.modules.payment.domain.value_objects import (
    DisputeStatus,
    FundDispositionStatus,
    Money,
    OperationStatus,
    PaymentAttemptStatus,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(slots=True)
class PaymentAttempt:
    id: EntityId
    booking_id: EntityId
    student_id: EntityId
    amount: Money
    idempotency_key: str
    status: PaymentAttemptStatus
    provider_name: str
    provider_reference: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    confirmed_at: datetime | None = None

    def record_late_success_signal(self) -> None:
        terminal_non_success = {
            PaymentAttemptStatus.EXPIRED,
            PaymentAttemptStatus.FAILED,
            PaymentAttemptStatus.CANCELLED,
        }
        if self.status not in terminal_non_success:
            raise ValueError(
                "Late success signal can only be recorded for terminal non-SUCCEEDED payment attempts."
            )


@dataclass(slots=True)
class Payment:
    id: EntityId
    payment_attempt_id: EntityId
    booking_id: EntityId
    student_id: EntityId
    amount: Money
    provider_reference: str
    confirmed_at: datetime


@dataclass(slots=True)
class ReleaseOperation:
    id: EntityId
    fund_disposition_id: EntityId
    amount: Money
    status: OperationStatus
    decision_id: EntityId
    provider_operation_reference: str | None = None
    requested_at: datetime = field(default_factory=datetime.now)
    confirmed_at: datetime | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.amount.amount_kobo < 0:
            raise ValueError("Release amount cannot be negative.")


@dataclass(slots=True)
class RefundOperation:
    id: EntityId
    fund_disposition_id: EntityId
    amount: Money
    status: OperationStatus
    decision_id: EntityId
    provider_operation_reference: str | None = None
    requested_at: datetime = field(default_factory=datetime.now)
    confirmed_at: datetime | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.amount.amount_kobo < 0:
            raise ValueError("Refund amount cannot be negative.")


@dataclass(slots=True)
class FundDisposition:
    id: EntityId
    payment_id: EntityId
    held_amount_kobo: int
    status: FundDispositionStatus
    created_at: datetime = field(default_factory=datetime.now)
    release_operations: list[ReleaseOperation] = field(default_factory=list)
    refund_operations: list[RefundOperation] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.held_amount_kobo < 0:
            raise ValueError("Held amount cannot be negative.")
        self._validate_balance()

    @property
    def released_amount_kobo(self) -> int:
        return sum(
            op.amount.amount_kobo
            for op in self.release_operations
            if op.status == OperationStatus.SUCCEEDED
        )

    @property
    def refunded_amount_kobo(self) -> int:
        return sum(
            op.amount.amount_kobo
            for op in self.refund_operations
            if op.status == OperationStatus.SUCCEEDED
        )

    @property
    def remaining_releasable_kobo(self) -> int:
        return self.held_amount_kobo - self.released_amount_kobo - self.refunded_amount_kobo

    def _validate_balance(self) -> None:
        if self.remaining_releasable_kobo < 0:
            raise ValueError("FundDisposition remaining balance cannot go negative.")

    def add_release_operation(self, op: ReleaseOperation) -> None:
        self.release_operations.append(op)
        self._validate_balance()

    def add_refund_operation(self, op: RefundOperation) -> None:
        self.refund_operations.append(op)
        self._validate_balance()


@dataclass(slots=True)
class Dispute:
    id: EntityId
    fund_disposition_id: EntityId
    raised_by: EntityId
    reason: str
    status: DisputeStatus
    raised_at: datetime = field(default_factory=datetime.now)
    resolved_at: datetime | None = None
    resolved_by: EntityId | None = None
    resolution_notes: str | None = None

    def __post_init__(self) -> None:
        if not self.reason or not self.reason.strip():
            raise ValueError("Dispute reason is required.")
