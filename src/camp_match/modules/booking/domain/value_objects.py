from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BookingStatus(Enum):
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


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
