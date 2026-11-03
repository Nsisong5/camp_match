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


class TargetType(StrEnum):
    CONVERSATION = "CONVERSATION"
    BOOKING = "BOOKING"
    VERIFICATION_CASE = "VERIFICATION_CASE"
    SAFETY_REPORT = "SAFETY_REPORT"
    LISTING = "LISTING"


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

    def __post_init__(self) -> None:
        if self.group_key is not None and not self.type.is_collapsible:
            raise ValueError(
                f"Notification type {self.type.value} is not collapsible "
                "but group_key was provided."
            )
