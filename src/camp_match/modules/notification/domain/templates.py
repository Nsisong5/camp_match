"""Notification rendering templates."""
from __future__ import annotations

from camp_match.modules.notification.domain.value_objects import NotificationType

_TEMPLATES: dict[NotificationType, tuple[str, str]] = {
    NotificationType.MESSAGE_NEW: ("New message", "You have a new message."),
    NotificationType.BOOKING_CREATED_PROVIDER: (
        "New booking",
        "A student has reserved one of your listings. Payment is pending.",
    ),
    NotificationType.BOOKING_CONFIRMED_STUDENT: (
        "Booking confirmed",
        "Your booking has been confirmed.",
    ),
    NotificationType.BOOKING_CONFIRMED_PROVIDER: (
        "Booking confirmed",
        "A booking on one of your listings has been confirmed.",
    ),
    NotificationType.BOOKING_CANCELLED_STUDENT: (
        "Booking cancelled",
        "Your booking was cancelled.",
    ),
    NotificationType.BOOKING_CANCELLED_PROVIDER: (
        "Booking cancelled",
        "A booking on one of your listings was cancelled.",
    ),
    NotificationType.BOOKING_EXPIRED_STUDENT: (
        "Booking expired",
        "Your booking hold expired because payment wasn't completed.",
    ),
    NotificationType.VERIFICATION_VERIFIED: (
        "Verification approved",
        "Your verification was approved.",
    ),
    NotificationType.VERIFICATION_REJECTED: (
        "Verification not approved",
        "Your verification was not approved. Open the case for details.",
    ),
    NotificationType.VERIFICATION_REVOKED: (
        "Verification revoked",
        "Your verification was revoked. Open the case for details.",
    ),
    NotificationType.SAFETY_REPORT_RECEIVED: (
        "Report received",
        "Thank you. We've received your report and will review it.",
    ),
    NotificationType.SAFETY_REPORT_REVIEWED: (
        "Report reviewed",
        "We've reviewed your report. Thank you for helping keep Camp Match safe.",
    ),
    NotificationType.SAFETY_WARNING_ISSUED: (
        "Safety notice",
        "You've received a warning about activity on your account. Please follow Camp Match's community and safety guidelines.",
    ),
    NotificationType.SAFETY_COMMUNICATION_RESTRICTED: (
        "Messaging restricted",
        "Your ability to send messages has been restricted. Contact support if you have questions.",
    ),
    NotificationType.SAFETY_LISTING_SUSPENDED: (
        "Listing suspended",
        "One of your listings has been suspended following a safety review. Contact support if you have questions.",
    ),
    NotificationType.SAFETY_RESTRICTION_LIFTED: (
        "Restriction lifted",
        "A safety restriction on your account has been lifted.",
    ),
}


def render(ntype: NotificationType) -> tuple[str, str]:
    if ntype not in _TEMPLATES:
        raise ValueError(f"Unknown notification type: {ntype}")
    return _TEMPLATES[ntype]
