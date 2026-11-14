"""Recipient policies for Notification module."""
from __future__ import annotations

import structlog
from collections.abc import Awaitable, Callable
from typing import Any

from camp_match.modules.notification.application.parsing.event_parsers import (
    BookingEventData,
    ListingSuspendedEvent,
    ListingSuspensionLiftedEvent,
    MessageNewEvent,
    SafetyUpdateEventData,
    VerificationEventData,
    parse_event,
)
from camp_match.modules.notification.domain.value_objects import (
    NotificationAction,
    NotificationDraft,
    NotificationTarget,
    NotificationType,
    TargetType,
)
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


async def resolve_recipients(
    event_type: str,
    payload: dict[str, Any],
    get_owner: Callable[[EntityId], Awaitable[EntityId | None]],
) -> tuple[
    list[NotificationDraft],
    list[tuple[TargetType, EntityId, list[NotificationAction]]],
]:
    parsed = parse_event(event_type, payload)
    drafts: list[NotificationDraft] = []
    actions_to_resolve: list[
        tuple[TargetType, EntityId, list[NotificationAction]]
    ] = []

    if event_type == NotificationType.MESSAGE_NEW.value:
        assert isinstance(parsed, MessageNewEvent)
        drafts.append(
            NotificationDraft(
                recipient_id=parsed.recipient_id,
                type=NotificationType.MESSAGE_NEW,
                target=NotificationTarget(
                    type=TargetType.CONVERSATION, id=parsed.conversation_id
                ),
                group_key=f"message:{parsed.conversation_id.value}",
            )
        )

    elif event_type in {
        NotificationType.BOOKING_CREATED_PROVIDER.value,
        NotificationType.BOOKING_CREATED_STUDENT.value,
    }:
        assert isinstance(parsed, BookingEventData)
        owner_id = await get_owner(parsed.property_id)
        if owner_id:
            drafts.append(
                NotificationDraft(
                    recipient_id=owner_id,
                    type=NotificationType.BOOKING_CREATED_PROVIDER,
                    target=NotificationTarget(
                        type=TargetType.BOOKING, id=parsed.booking_id
                    ),
                )
            )
        else:
            logger.warning(
                "notification_no_recipient", property_id=parsed.property_id.value
            )

        drafts.append(
            NotificationDraft(
                recipient_id=parsed.student_id,
                type=NotificationType.BOOKING_CREATED_STUDENT,
                target=NotificationTarget(
                    type=TargetType.BOOKING, id=parsed.booking_id
                ),
                action=NotificationAction.COMPLETE_PAYMENT,
            )
        )

    elif event_type in {
        NotificationType.BOOKING_CONFIRMED_STUDENT.value,
        NotificationType.BOOKING_CONFIRMED_PROVIDER.value,
        "BookingConfirmed",
    }:
        assert isinstance(parsed, BookingEventData)
        owner_id = await get_owner(parsed.property_id)

        drafts.append(
            NotificationDraft(
                recipient_id=parsed.student_id,
                type=NotificationType.BOOKING_CONFIRMED_STUDENT,
                target=NotificationTarget(
                    type=TargetType.BOOKING, id=parsed.booking_id
                ),
            )
        )
        if owner_id:
            drafts.append(
                NotificationDraft(
                    recipient_id=owner_id,
                    type=NotificationType.BOOKING_CONFIRMED_PROVIDER,
                    target=NotificationTarget(
                        type=TargetType.BOOKING, id=parsed.booking_id
                    ),
                    action=NotificationAction.OFFER_HANDOVER,
                )
            )
        actions_to_resolve.append(
            (
                TargetType.BOOKING,
                parsed.booking_id,
                [NotificationAction.COMPLETE_PAYMENT],
            )
        )

    elif event_type in {
        NotificationType.HANDOVER_OFFERED_STUDENT.value,
        "HandoverOffered",
    }:
        assert isinstance(parsed, BookingEventData)
        drafts.append(
            NotificationDraft(
                recipient_id=parsed.student_id,
                type=NotificationType.HANDOVER_OFFERED_STUDENT,
                target=NotificationTarget(
                    type=TargetType.BOOKING, id=parsed.booking_id
                ),
                action=NotificationAction.ACCEPT_HANDOVER,
            )
        )
        actions_to_resolve.append(
            (
                TargetType.BOOKING,
                parsed.booking_id,
                [NotificationAction.OFFER_HANDOVER],
            )
        )

    elif event_type in {
        NotificationType.HANDOVER_ACCEPTED_PROVIDER.value,
        "HandoverAccepted",
    }:
        assert isinstance(parsed, BookingEventData)
        owner_id = await get_owner(parsed.property_id)
        if owner_id:
            drafts.append(
                NotificationDraft(
                    recipient_id=owner_id,
                    type=NotificationType.HANDOVER_ACCEPTED_PROVIDER,
                    target=NotificationTarget(
                        type=TargetType.BOOKING, id=parsed.booking_id
                    ),
                )
            )
        actions_to_resolve.append(
            (
                TargetType.BOOKING,
                parsed.booking_id,
                [NotificationAction.ACCEPT_HANDOVER],
            )
        )

    elif event_type in {
        NotificationType.BOOKING_CANCELLED_STUDENT.value,
        NotificationType.BOOKING_CANCELLED_PROVIDER.value,
        NotificationType.BOOKING_EXPIRED_STUDENT.value,
    }:
        assert isinstance(parsed, BookingEventData)
        owner_id = await get_owner(parsed.property_id)
        student_id = parsed.student_id

        if event_type == NotificationType.BOOKING_EXPIRED_STUDENT.value:
            drafts.append(
                NotificationDraft(
                    recipient_id=student_id,
                    type=NotificationType.BOOKING_EXPIRED_STUDENT,
                    target=NotificationTarget(
                        type=TargetType.BOOKING, id=parsed.booking_id
                    ),
                )
            )
        else:
            cancelled_by = parsed.cancelled_by
            notify_student = cancelled_by != student_id
            notify_provider = owner_id and cancelled_by != owner_id

            if (
                not owner_id
                and event_type == NotificationType.BOOKING_CANCELLED_PROVIDER.value
            ):
                logger.warning(
                    "notification_no_recipient", property_id=parsed.property_id.value
                )

            if event_type == NotificationType.BOOKING_CANCELLED_STUDENT.value and notify_student:
                drafts.append(
                    NotificationDraft(
                        recipient_id=student_id,
                        type=NotificationType.BOOKING_CANCELLED_STUDENT,
                        target=NotificationTarget(
                            type=TargetType.BOOKING, id=parsed.booking_id
                        ),
                    )
                )
            if event_type == NotificationType.BOOKING_CANCELLED_PROVIDER.value and notify_provider and owner_id:
                drafts.append(
                    NotificationDraft(
                        recipient_id=owner_id,
                        type=NotificationType.BOOKING_CANCELLED_PROVIDER,
                        target=NotificationTarget(
                            type=TargetType.BOOKING, id=parsed.booking_id
                        ),
                    )
                )

        actions_to_resolve.append(
            (
                TargetType.BOOKING,
                parsed.booking_id,
                [
                    NotificationAction.COMPLETE_PAYMENT,
                    NotificationAction.OFFER_HANDOVER,
                    NotificationAction.ACCEPT_HANDOVER,
                ],
            )
        )

    elif event_type in {
        NotificationType.BOOKING_INVALIDATED_STUDENT.value,
        NotificationType.BOOKING_INVALIDATED_PROVIDER.value,
        "BookingInvalidated",
    }:
        assert isinstance(parsed, BookingEventData)
        owner_id = await get_owner(parsed.property_id)

        drafts.append(
            NotificationDraft(
                recipient_id=parsed.student_id,
                type=NotificationType.BOOKING_INVALIDATED_STUDENT,
                target=NotificationTarget(
                    type=TargetType.BOOKING, id=parsed.booking_id
                ),
            )
        )
        if owner_id and parsed.reason_code != "OWNER_ACCOUNT_DISABLED":
            drafts.append(
                NotificationDraft(
                    recipient_id=owner_id,
                    type=NotificationType.BOOKING_INVALIDATED_PROVIDER,
                    target=NotificationTarget(
                        type=TargetType.BOOKING, id=parsed.booking_id
                    ),
                    group_key=f"booking-invalidated:{parsed.listing_id.value}",
                )
            )

        actions_to_resolve.append(
            (
                TargetType.BOOKING,
                parsed.booking_id,
                [
                    NotificationAction.COMPLETE_PAYMENT,
                    NotificationAction.OFFER_HANDOVER,
                    NotificationAction.ACCEPT_HANDOVER,
                ],
            )
        )

    elif event_type in {
        NotificationType.BOOKING_HANDOVER_REMINDER_PROVIDER.value,
        NotificationType.BOOKING_ACCEPTANCE_REMINDER_STUDENT.value,
        "BookingReminderDue",
    }:
        assert isinstance(parsed, BookingEventData)
        owner_id = await get_owner(parsed.property_id)
        reminder_type = parsed.reminder_type
        if reminder_type == "HANDOVER_NOT_OFFERED" and owner_id:
            drafts.append(
                NotificationDraft(
                    recipient_id=owner_id,
                    type=NotificationType.BOOKING_HANDOVER_REMINDER_PROVIDER,
                    target=NotificationTarget(
                        type=TargetType.BOOKING, id=parsed.booking_id
                    ),
                )
            )
        elif reminder_type == "ACCEPTANCE_PENDING":
            drafts.append(
                NotificationDraft(
                    recipient_id=parsed.student_id,
                    type=NotificationType.BOOKING_ACCEPTANCE_REMINDER_STUDENT,
                    target=NotificationTarget(
                        type=TargetType.BOOKING, id=parsed.booking_id
                    ),
                )
            )

    elif event_type in {
        NotificationType.HOUSING_LISTING_SUSPENDED.value,
        "ListingSuspended",
    }:
        assert isinstance(parsed, ListingSuspendedEvent)
        if parsed.reason_code != "OWNER_ACCOUNT_DISABLED":
            drafts.append(
                NotificationDraft(
                    recipient_id=parsed.owner_id,
                    type=NotificationType.HOUSING_LISTING_SUSPENDED,
                    target=NotificationTarget(
                        type=TargetType.LISTING, id=parsed.listing_id
                    ),
                )
            )

    elif event_type in {
        NotificationType.HOUSING_LISTING_SUSPENSION_LIFTED.value,
        "ListingSuspensionLifted",
    }:
        assert isinstance(parsed, ListingSuspensionLiftedEvent)
        drafts.append(
            NotificationDraft(
                recipient_id=parsed.owner_id,
                type=NotificationType.HOUSING_LISTING_SUSPENSION_LIFTED,
                target=NotificationTarget(
                    type=TargetType.LISTING, id=parsed.listing_id
                ),
            )
        )

    elif event_type in {
        NotificationType.PAYMENT_FAILED_STUDENT.value,
        NotificationType.PAYMENT_LATE_STUDENT.value,
        NotificationType.PAYMENT_REVIEW_STUDENT.value,
        "PaymentOutcomeRecorded",
    }:
        assert isinstance(parsed, BookingEventData)
        outcome = parsed.outcome
        type_map = {
            "FAILED": NotificationType.PAYMENT_FAILED_STUDENT,
            "LATE": NotificationType.PAYMENT_LATE_STUDENT,
            "REVIEW": NotificationType.PAYMENT_REVIEW_STUDENT,
        }
        if outcome in type_map:
            drafts.append(
                NotificationDraft(
                    recipient_id=parsed.student_id,
                    type=type_map[outcome],
                    target=NotificationTarget(
                        type=TargetType.BOOKING, id=parsed.booking_id
                    ),
                )
            )

    elif event_type in {
        NotificationType.VERIFICATION_VERIFIED.value,
        NotificationType.VERIFICATION_REJECTED.value,
        NotificationType.VERIFICATION_REVOKED.value,
    }:
        assert isinstance(parsed, VerificationEventData)
        recipient_id: EntityId | None = None
        if parsed.target_type == TargetType.CONVERSATION:
            recipient_id = parsed.target_id
        elif parsed.target_type == TargetType.VERIFICATION_CASE:
            recipient_id = await get_owner(parsed.target_id)

        if recipient_id:
            drafts.append(
                NotificationDraft(
                    recipient_id=recipient_id,
                    type=NotificationType(event_type),
                    target=NotificationTarget(
                        type=parsed.target_type, id=parsed.target_id
                    ),
                )
            )

    elif event_type in {
        NotificationType.SAFETY_REPORT_RECEIVED.value,
        NotificationType.SAFETY_REPORT_REVIEWED.value,
        NotificationType.SAFETY_WARNING_ISSUED.value,
        NotificationType.SAFETY_COMMUNICATION_RESTRICTED.value,
        NotificationType.SAFETY_LISTING_SUSPENDED.value,
        NotificationType.SAFETY_RESTRICTION_LIFTED.value,
        "SafetyUpdatePublished",
    }:
        assert isinstance(parsed, SafetyUpdateEventData)
        drafts.append(
            NotificationDraft(
                recipient_id=parsed.recipient_id,
                type=NotificationType(event_type)
                if event_type in {t.value for t in NotificationType}
                else NotificationType.SAFETY_WARNING_ISSUED,
                target=NotificationTarget(
                    type=TargetType.SAFETY_REPORT, id=parsed.reference_id
                )
                if parsed.reference_id
                else None,
            )
        )

    return drafts, actions_to_resolve
