"""Event registration for Notification module."""
from __future__ import annotations

from typing import Any

from camp_match.modules.booking.domain.events import (
    BookingCancelled,
    BookingConfirmed,
    BookingCreated,
    BookingExpired,
)
from camp_match.modules.messaging.domain.events import MessageCreated
from camp_match.modules.notification.adapters.events.subscribers import (
    create_handler,
)
from camp_match.modules.verification.domain.events import VerificationDecisionRecorded
from camp_match.modules.trust_safety.application.ports.events import (
    SafetyUpdatePublished,
)
from camp_match.shared_kernel.application.event_bus import EventBus


def register_notification_subscribers(
    event_bus: EventBus,
    session_factory: Any,
    clock: Any,
    settings: Any,
) -> None:
    debug_fail = False
    if settings.app_env in ("local", "test") and getattr(
        settings, "notification_debug_fail_processing", False
    ):
        debug_fail = True

    for event_cls in [
        MessageCreated,
        BookingCreated,
        BookingConfirmed,
        BookingCancelled,
        BookingExpired,
        VerificationDecisionRecorded,
        SafetyUpdatePublished,
    ]:
        handler = create_handler(
            event_cls, session_factory, clock, settings, debug_fail
        )
        event_bus.subscribe(event_cls, handler)
