"""Notification domain value objects and enums."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from camp_match.shared_kernel.domain.identifiers import EntityId


class NotificationCategory(StrEnum):
    MESSAGE = "MESSAGE"
    BOOKING = "BOOKING"
    VERIFICATION = "VERIFICATION"
    SAFETY = "SAFETY"
    HOUSING = "HOUSING"
    PAYMENT = "PAYMENT"


class TargetType(StrEnum):
    CONVERSATION = "CONVERSATION"
    BOOKING = "BOOKING"
    VERIFICATION_CASE = "VERIFICATION_CASE"
    SAFETY_REPORT = "SAFETY_REPORT"
    LISTING = "LISTING"


class NotificationAction(StrEnum):
    COMPLETE_PAYMENT = "COMPLETE_PAYMENT"
    OFFER_HANDOVER = "OFFER_HANDOVER"
    ACCEPT_HANDOVER = "ACCEPT_HANDOVER"
    RELEASE_FUNDS = "RELEASE_FUNDS"


class InboxStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    REJECTED = "REJECTED"
    DEAD = "DEAD"


class NotificationType(StrEnum):
    MESSAGE_NEW = "message.new"
    BOOKING_CREATED_PROVIDER = "booking.created.provider"
    BOOKING_CONFIRMED_STUDENT = "booking.confirmed.student"
    BOOKING_CONFIRMED_PROVIDER = "booking.confirmed.provider"
    BOOKING_CANCELLED_STUDENT = "booking.cancelled.student"
    BOOKING_CANCELLED_PROVIDER = "booking.cancelled.provider"
    BOOKING_EXPIRED_STUDENT = "booking.expired.student"
    VERIFICATION_VERIFIED = "verification.verified"
    VERIFICATION_REJECTED = "verification.rejected"
    VERIFICATION_REVOKED = "verification.revoked"
    SAFETY_REPORT_RECEIVED = "safety.report_received"
    SAFETY_REPORT_REVIEWED = "safety.report_reviewed"
    SAFETY_WARNING_ISSUED = "safety.warning_issued"
    SAFETY_COMMUNICATION_RESTRICTED = "safety.communication_restricted"
    SAFETY_LISTING_SUSPENDED = "safety.listing_suspended"
    SAFETY_RESTRICTION_LIFTED = "safety.restriction_lifted"
    BOOKING_CREATED_STUDENT = "booking.created.student"
    HANDOVER_OFFERED_STUDENT = "handover.offered.student"
    HANDOVER_ACCEPTED_PROVIDER = "handover.accepted.provider"
    BOOKING_HANDOVER_REMINDER_PROVIDER = "booking.handover_reminder.provider"
    BOOKING_ACCEPTANCE_REMINDER_STUDENT = "booking.acceptance_reminder.student"
    BOOKING_INVALIDATED_STUDENT = "booking.invalidated.student"
    BOOKING_INVALIDATED_PROVIDER = "booking.invalidated.provider"
    HOUSING_LISTING_SUSPENDED = "housing.listing_suspended"
    HOUSING_LISTING_SUSPENSION_LIFTED = "housing.listing_suspension_lifted"
    PAYMENT_FAILED_STUDENT = "payment.failed.student"
    PAYMENT_LATE_STUDENT = "payment.late.student"
    PAYMENT_REVIEW_STUDENT = "payment.review.student"
    PAYMENT_RELEASE_DUE_STAFF = "payment.release_due.staff"
    PAYMENT_AUTO_RELEASE_WARNING_FIRST_STAFF = "payment.auto_release_warning_first.staff"
    PAYMENT_AUTO_RELEASE_WARNING_REMINDER_STAFF = "payment.auto_release_warning_reminder.staff"
    PAYMENT_AUTO_RELEASE_WARNING_FINAL_STAFF = "payment.auto_release_warning_final.staff"
    PAYMENT_DISPUTE_RAISED_STAFF = "payment.dispute_raised.staff"
    PAYMENT_FUNDS_AUTO_RELEASED_STAFF = "payment.funds_auto_released.staff"

    @property
    def category(self) -> NotificationCategory:
        _mapping = {
            NotificationType.MESSAGE_NEW: NotificationCategory.MESSAGE,
            NotificationType.BOOKING_CREATED_PROVIDER: NotificationCategory.BOOKING,
            NotificationType.BOOKING_CONFIRMED_STUDENT: NotificationCategory.BOOKING,
            NotificationType.BOOKING_CONFIRMED_PROVIDER: NotificationCategory.BOOKING,
            NotificationType.BOOKING_CANCELLED_STUDENT: NotificationCategory.BOOKING,
            NotificationType.BOOKING_CANCELLED_PROVIDER: NotificationCategory.BOOKING,
            NotificationType.BOOKING_EXPIRED_STUDENT: NotificationCategory.BOOKING,
            NotificationType.VERIFICATION_VERIFIED: NotificationCategory.VERIFICATION,
            NotificationType.VERIFICATION_REJECTED: NotificationCategory.VERIFICATION,
            NotificationType.VERIFICATION_REVOKED: NotificationCategory.VERIFICATION,
            NotificationType.SAFETY_REPORT_RECEIVED: NotificationCategory.SAFETY,
            NotificationType.SAFETY_REPORT_REVIEWED: NotificationCategory.SAFETY,
            NotificationType.SAFETY_WARNING_ISSUED: NotificationCategory.SAFETY,
            NotificationType.SAFETY_COMMUNICATION_RESTRICTED: NotificationCategory.SAFETY,
            NotificationType.SAFETY_LISTING_SUSPENDED: NotificationCategory.SAFETY,
            NotificationType.SAFETY_RESTRICTION_LIFTED: NotificationCategory.SAFETY,
            NotificationType.BOOKING_CREATED_STUDENT: NotificationCategory.BOOKING,
            NotificationType.HANDOVER_OFFERED_STUDENT: NotificationCategory.BOOKING,
            NotificationType.HANDOVER_ACCEPTED_PROVIDER: NotificationCategory.BOOKING,
            NotificationType.BOOKING_HANDOVER_REMINDER_PROVIDER: NotificationCategory.BOOKING,
            NotificationType.BOOKING_ACCEPTANCE_REMINDER_STUDENT: NotificationCategory.BOOKING,
            NotificationType.BOOKING_INVALIDATED_STUDENT: NotificationCategory.BOOKING,
            NotificationType.BOOKING_INVALIDATED_PROVIDER: NotificationCategory.BOOKING,
            NotificationType.HOUSING_LISTING_SUSPENDED: NotificationCategory.HOUSING,
            NotificationType.HOUSING_LISTING_SUSPENSION_LIFTED: NotificationCategory.HOUSING,
            NotificationType.PAYMENT_FAILED_STUDENT: NotificationCategory.PAYMENT,
            NotificationType.PAYMENT_LATE_STUDENT: NotificationCategory.PAYMENT,
            NotificationType.PAYMENT_REVIEW_STUDENT: NotificationCategory.PAYMENT,
            NotificationType.PAYMENT_RELEASE_DUE_STAFF: NotificationCategory.PAYMENT,
            NotificationType.PAYMENT_AUTO_RELEASE_WARNING_FIRST_STAFF: NotificationCategory.PAYMENT,
            NotificationType.PAYMENT_AUTO_RELEASE_WARNING_REMINDER_STAFF: NotificationCategory.PAYMENT,
            NotificationType.PAYMENT_AUTO_RELEASE_WARNING_FINAL_STAFF: NotificationCategory.PAYMENT,
            NotificationType.PAYMENT_DISPUTE_RAISED_STAFF: NotificationCategory.PAYMENT,
            NotificationType.PAYMENT_FUNDS_AUTO_RELEASED_STAFF: NotificationCategory.PAYMENT,
        }
        return _mapping[self]

    @property
    def is_collapsible(self) -> bool:
        _collapsible_mapping = {
            NotificationType.MESSAGE_NEW: True,
            NotificationType.BOOKING_CREATED_PROVIDER: False,
            NotificationType.BOOKING_CONFIRMED_STUDENT: False,
            NotificationType.BOOKING_CONFIRMED_PROVIDER: False,
            NotificationType.BOOKING_CANCELLED_STUDENT: False,
            NotificationType.BOOKING_CANCELLED_PROVIDER: False,
            NotificationType.BOOKING_EXPIRED_STUDENT: False,
            NotificationType.VERIFICATION_VERIFIED: False,
            NotificationType.VERIFICATION_REJECTED: False,
            NotificationType.VERIFICATION_REVOKED: False,
            NotificationType.SAFETY_REPORT_RECEIVED: False,
            NotificationType.SAFETY_REPORT_REVIEWED: False,
            NotificationType.SAFETY_WARNING_ISSUED: False,
            NotificationType.SAFETY_COMMUNICATION_RESTRICTED: False,
            NotificationType.SAFETY_LISTING_SUSPENDED: False,
            NotificationType.SAFETY_RESTRICTION_LIFTED: False,
            NotificationType.BOOKING_CREATED_STUDENT: False,
            NotificationType.HANDOVER_OFFERED_STUDENT: False,
            NotificationType.HANDOVER_ACCEPTED_PROVIDER: False,
            NotificationType.BOOKING_HANDOVER_REMINDER_PROVIDER: False,
            NotificationType.BOOKING_ACCEPTANCE_REMINDER_STUDENT: False,
            NotificationType.BOOKING_INVALIDATED_STUDENT: False,
            NotificationType.BOOKING_INVALIDATED_PROVIDER: True,
            NotificationType.HOUSING_LISTING_SUSPENDED: False,
            NotificationType.HOUSING_LISTING_SUSPENSION_LIFTED: False,
            NotificationType.PAYMENT_FAILED_STUDENT: False,
            NotificationType.PAYMENT_LATE_STUDENT: False,
            NotificationType.PAYMENT_REVIEW_STUDENT: False,
            NotificationType.PAYMENT_RELEASE_DUE_STAFF: False,
            NotificationType.PAYMENT_AUTO_RELEASE_WARNING_FIRST_STAFF: False,
            NotificationType.PAYMENT_AUTO_RELEASE_WARNING_REMINDER_STAFF: False,
            NotificationType.PAYMENT_AUTO_RELEASE_WARNING_FINAL_STAFF: False,
            NotificationType.PAYMENT_DISPUTE_RAISED_STAFF: False,
            NotificationType.PAYMENT_FUNDS_AUTO_RELEASED_STAFF: False,
        }
        return _collapsible_mapping[self]


@dataclass(frozen=True)
class NotificationTarget:
    type: TargetType
    id: EntityId


@dataclass(frozen=True)
class NotificationDraft:
    recipient_id: EntityId
    type: NotificationType
    target: NotificationTarget | None = None
    group_key: str | None = None
    action: NotificationAction | None = None

    def __post_init__(self) -> None:
        if self.group_key is not None and not self.type.is_collapsible:
            raise ValueError(
                f"Notification type {self.type.value} is not collapsible "
                "but group_key was provided."
            )
        if self.action is not None and self.target is None:
            raise ValueError("Action requires a target.")
