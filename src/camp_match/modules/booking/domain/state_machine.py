from __future__ import annotations

from camp_match.modules.booking.domain.entities import Booking
from camp_match.modules.booking.domain.value_objects import BookingStatus


def can_transition(current: BookingStatus, target: BookingStatus) -> bool:
    if current in {BookingStatus.CANCELLED, BookingStatus.EXPIRED}:
        return False

    if current == BookingStatus.AWAITING_PAYMENT:
        return target in {BookingStatus.CONFIRMED, BookingStatus.CANCELLED, BookingStatus.EXPIRED}

    if current == BookingStatus.CONFIRMED:
        return target == BookingStatus.CANCELLED

    return False


def transition(booking: Booking, target: BookingStatus) -> None:
    if not can_transition(booking.status, target):
        raise ValueError(
            f"Invalid booking state transition from {booking.status.value} to {target.value}."
        )
    booking.status = target
