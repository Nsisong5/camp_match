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
        "Action needed: arrange handover",
        "A booking on one of your listings is confirmed and paid. Arrange access with the student, then confirm the handover in the app.",
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
    NotificationType.BOOKING_CREATED_STUDENT: (
        "Complete your payment",
        "Your booking is on hold. Complete payment before the hold expires to keep it.",
    ),
    NotificationType.HANDOVER_OFFERED_STUDENT: (
        "Confirm you have access",
        "Your host says access to your place is ready. Confirm in the app once you have it.",
    ),
    NotificationType.HANDOVER_ACCEPTED_PROVIDER: (
        "Handover confirmed",
        "The student confirmed they received access.",
    ),
    NotificationType.BOOKING_HANDOVER_REMINDER_PROVIDER: (
        "Reminder: confirm handover",
        "A paid booking on one of your listings is still waiting for you to confirm handover.",
    ),
    NotificationType.BOOKING_ACCEPTANCE_REMINDER_STUDENT: (
        "Reminder: confirm access",
        "Your host offered access to your place. Please confirm in the app once you have it.",
    ),
    NotificationType.BOOKING_INVALIDATED_STUDENT: (
        "Booking cancelled",
        "Your booking was cancelled because the listing is no longer available. If you already paid, our team will review your payment.",
    ),
    NotificationType.BOOKING_INVALIDATED_PROVIDER: (
        "Bookings cancelled",
        "Bookings on one of your suspended listings were cancelled.",
    ),
    NotificationType.HOUSING_LISTING_SUSPENDED: (
        "Listing suspended",
        "One of your listings has been suspended and is no longer visible. Existing bookings on it are being cancelled. Contact support if you have questions.",
    ),
    NotificationType.HOUSING_LISTING_SUSPENSION_LIFTED: (
        "Listing suspension lifted",
        "A suspension on one of your listings was lifted. It is not live yet — review it and publish it again when you're ready.",
    ),
    NotificationType.PAYMENT_FAILED_STUDENT: (
        "Payment failed",
        "Your payment didn't go through. If your booking hold hasn't expired, you can try again.",
    ),
    NotificationType.PAYMENT_LATE_STUDENT: (
        "Payment received late",
        "We received your payment after your booking hold expired. Our team will review it.",
    ),
    NotificationType.PAYMENT_REVIEW_STUDENT: (
        "Payment under review",
        "There was a problem confirming your payment. Our team will review it.",
    ),
}


def render(ntype: NotificationType) -> tuple[str, str]:
    if ntype not in _TEMPLATES:
        raise ValueError(f"Unknown notification type: {ntype}")
    return _TEMPLATES[ntype]
