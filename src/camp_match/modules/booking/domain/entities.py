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
    handover_offered_at: datetime | None = None
    handover_offered_by: EntityId | None = None
    handover_accepted_at: datetime | None = None

    def is_hold_expired(self, clock: Clock) -> bool:
        return self.status == BookingStatus.AWAITING_PAYMENT and self.expires_at < clock.now()

    def confirm_handover_offered(self, actor_id: EntityId, now: datetime) -> None:
        if self.status != BookingStatus.CONFIRMED:
            raise ValueError("Booking must be confirmed before handover can be offered.")
        if self.handover_offered_at is not None:
            raise ValueError("Handover has already been offered.")
        self.handover_offered_at = now
        self.handover_offered_by = actor_id

    def confirm_handover_accepted(self, actor_id: EntityId, now: datetime) -> None:
        if self.status != BookingStatus.CONFIRMED:
            raise ValueError("Booking must be confirmed before handover can be accepted.")
        if self.handover_offered_at is None:
            raise ValueError("Handover must be offered by the scout before it can be accepted.")
        if self.handover_accepted_at is not None:
            raise ValueError("Handover has already been accepted.")
        if actor_id != self.student_id:
            raise ValueError("Only the booking student can confirm handover acceptance.")
        self.handover_accepted_at = now
