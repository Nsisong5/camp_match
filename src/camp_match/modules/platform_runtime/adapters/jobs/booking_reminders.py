"""Booking reminders job factory."""
from __future__ import annotations

from typing import Any

from camp_match.modules.booking.application.use_cases.publish_booking_reminders import (
    PublishBookingRemindersUseCase,
)


def build_booking_reminders_job(
    session_factory: Any,
    session: Any,
    clock: Any,
    settings: Any,
    event_bus: Any,
) -> Any:
    uc = PublishBookingRemindersUseCase(session_factory, clock, settings)

    async def run() -> int:
        return await uc()

    return run
