from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BookingStatus(Enum):
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ClosureCode(Enum):
    STUDENT_CANCELLED = "STUDENT_CANCELLED"
    PROVIDER_CANCELLED = "PROVIDER_CANCELLED"
    STAFF_CANCELLED = "STAFF_CANCELLED"
    HOLD_EXPIRED = "HOLD_EXPIRED"
    LISTING_SUSPENDED = "LISTING_SUSPENDED"
    OWNER_ACCOUNT_DISABLED = "OWNER_ACCOUNT_DISABLED"
    CANCELLED_UNSPECIFIED = "CANCELLED_UNSPECIFIED"

    @property
    def message(self) -> str:
        messages = {
            ClosureCode.STUDENT_CANCELLED: "Cancelled by the student.",
            ClosureCode.PROVIDER_CANCELLED: "Cancelled by the host.",
            ClosureCode.STAFF_CANCELLED: "Cancelled by Camp Match staff.",
            ClosureCode.HOLD_EXPIRED: "The hold expired because payment wasn't completed in time.",
            ClosureCode.LISTING_SUSPENDED: "Cancelled because the listing was suspended.",
            ClosureCode.OWNER_ACCOUNT_DISABLED: "Cancelled because the host's account is no longer active.",
            ClosureCode.CANCELLED_UNSPECIFIED: "Cancelled.",
        }
        return messages[self]


@dataclass(frozen=True, slots=True)
class Closure:
    code: str
    message: str


class Currency(Enum):
    NGN = "NGN"


class BillingPeriod(Enum):
    YEAR = "YEAR"
    SEMESTER = "SEMESTER"
    MONTH = "MONTH"


@dataclass(frozen=True, slots=True)
class PriceSnapshot:
    amount_kobo: int
    currency: Currency
    period: BillingPeriod

    def __post_init__(self) -> None:
        if self.amount_kobo < 0:
            raise ValueError("Price amount cannot be negative")
