from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Currency(Enum):
    NGN = "NGN"


@dataclass(frozen=True, slots=True)
class Money:
    amount_kobo: int
    currency: Currency = Currency.NGN

    def __post_init__(self) -> None:
        if self.amount_kobo < 0:
            raise ValueError("Money amount cannot be negative")


class PaymentAttemptStatus(Enum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class FundDispositionStatus(Enum):
    HELD = "HELD"
    DISPUTE_HOLD = "DISPUTE_HOLD"
    PARTIALLY_RELEASED = "PARTIALLY_RELEASED"
    RELEASED = "RELEASED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class OperationStatus(Enum):
    DECISION_RECORDED = "DECISION_RECORDED"
    PROVIDER_INITIATED = "PROVIDER_INITIATED"
    PROVIDER_PENDING = "PROVIDER_PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class DisputeStatus(Enum):
    OPEN = "OPEN"
    RESOLVED_RELEASE = "RESOLVED_RELEASE"
    RESOLVED_REFUND = "RESOLVED_REFUND"
    RESOLVED_PARTIAL = "RESOLVED_PARTIAL"


class DecisionOrigin(Enum):
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"


class LedgerEntryType(Enum):
    CHARGE = "CHARGE"
    HOLD_ALLOCATION = "HOLD_ALLOCATION"
    RELEASE = "RELEASE"
    REFUND = "REFUND"
    REVERSAL = "REVERSAL"
    CORRECTION = "CORRECTION"
