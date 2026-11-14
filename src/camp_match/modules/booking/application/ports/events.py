"""Booking public event contracts."""
from __future__ import annotations

from camp_match.modules.booking.domain.events import (
    BookingCancelled,
    BookingConfirmed,
    BookingCreated,
    BookingExpired,
    BookingInvalidated,
    BookingReminderDue,
    HandoverAccepted,
    HandoverOffered,
)

__all__ = [
    "BookingCreated",
    "BookingConfirmed",
    "BookingCancelled",
    "BookingExpired",
    "BookingInvalidated",
    "HandoverOffered",
    "HandoverAccepted",
    "BookingReminderDue",
]
