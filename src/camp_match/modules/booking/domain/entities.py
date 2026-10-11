from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from camp_match.modules.booking.domain.value_objects import BookingStatus, PriceSnapshot
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(slots=True)
class Booking:
    id: EntityId
    student_id: EntityId
    listing_id: EntityId
    unit_id: EntityId
    property_id: EntityId
    status: BookingStatus
    price: PriceSnapshot
    verification_confirmed_at_booking: bool
    idempotency_key: str
    expires_at: datetime
    created_at: datetime
    confirmed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancelled_by: EntityId | None = None
    cancellation_reason: str | None = None

    def is_hold_expired(self, clock: Clock) -> bool:
        return self.status == BookingStatus.AWAITING_PAYMENT and self.expires_at < clock.now()
