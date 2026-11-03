"""Recipient policies for Notification module."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from camp_match.modules.notification.application.parsing.event_parsers import (
    BookingEventData,
    MessageNewEvent,
    SafetyUpdateEventData,
    VerificationEventData,
    parse_event,
)
from camp_match.modules.notification.domain.value_objects import (
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
) -> list[NotificationDraft]:
    parsed = parse_event(event_type, payload)
    drafts: list[NotificationDraft] = []

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

    elif event_type == NotificationType.BOOKING_CREATED_PROVIDER.value:
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
            logger.warning("notification_no_recipient", property_id=parsed.property_id.value)

    elif event_type in {
        NotificationType.BOOKING_CONFIRMED_STUDENT.value,
        NotificationType.BOOKING_CONFIRMED_PROVIDER.value,
    }:
        assert isinstance(parsed, BookingEventData)
        owner_id = await get_owner(parsed.property_id)
        if event_type == NotificationType.BOOKING_CONFIRMED_STUDENT.value:
            drafts.append(
                NotificationDraft(
                    recipient_id=parsed.student_id,
                    type=NotificationType.BOOKING_CONFIRMED_STUDENT,
                    target=NotificationTarget(
                        type=TargetType.BOOKING, id=parsed.booking_id
                    ),
                )
            )
        elif event_type == NotificationType.BOOKING_CONFIRMED_PROVIDER.value:
            if owner_id:
                drafts.append(
                    NotificationDraft(
                        recipient_id=owner_id,
                        type=NotificationType.BOOKING_CONFIRMED_PROVIDER,
                        target=NotificationTarget(
                            type=TargetType.BOOKING, id=parsed.booking_id
                        ),
                    )
                )
            else:
                logger.warning("notification_no_recipient", property_id=parsed.property_id.value)

    elif event_type in {
        NotificationType.BOOKING_CANCELLED_STUDENT.value,
        NotificationType.BOOKING_CANCELLED_PROVIDER.value,
    }:
        assert isinstance(parsed, BookingEventData)
        owner_id = await get_owner(parsed.property_id)
        student_id = parsed.student_id
        cancelled_by = parsed.cancelled_by

        notify_student = cancelled_by != student_id
        notify_provider = owner_id and cancelled_by != owner_id

        if not owner_id and event_type == NotificationType.BOOKING_CANCELLED_PROVIDER.value:
            logger.warning("notification_no_recipient", property_id=parsed.property_id.value)

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

    elif event_type == NotificationType.BOOKING_EXPIRED_STUDENT.value:
        assert isinstance(parsed, BookingEventData)
        drafts.append(
            NotificationDraft(
                recipient_id=parsed.student_id,
                type=NotificationType.BOOKING_EXPIRED_STUDENT,
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
        if parsed.target_type == TargetType.CONVERSATION:  # Used as marker for PROVIDER in parser
            recipient_id = parsed.target_id
        else:
            recipient_id = await get_owner(parsed.target_id)
            if not recipient_id:
                logger.warning("notification_no_recipient", target_id=parsed.target_id.value)

        if recipient_id:
            ntype = NotificationType(event_type)
            drafts.append(
                NotificationDraft(
                    recipient_id=recipient_id,
                    type=ntype,
                    target=NotificationTarget(
                        type=TargetType.VERIFICATION_CASE, id=parsed.case_id
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
        kind_map = {
            "REPORT_RECEIVED": NotificationType.SAFETY_REPORT_RECEIVED,
            "REPORT_REVIEWED": NotificationType.SAFETY_REPORT_REVIEWED,
            "WARNING_ISSUED": NotificationType.SAFETY_WARNING_ISSUED,
            "COMMUNICATION_RESTRICTED": NotificationType.SAFETY_COMMUNICATION_RESTRICTED,
            "LISTING_SUSPENDED": NotificationType.SAFETY_LISTING_SUSPENDED,
            "RESTRICTION_LIFTED": NotificationType.SAFETY_RESTRICTION_LIFTED,
        }
        if parsed.kind not in kind_map:
            raise ValueError(f"Unknown safety update kind: {parsed.kind}")
        ntype = kind_map[parsed.kind]

        target = None
        if parsed.reference_type == "SAFETY_REPORT" and parsed.reference_id:
            target = NotificationTarget(type=TargetType.SAFETY_REPORT, id=parsed.reference_id)
        elif parsed.reference_type == "LISTING" and parsed.reference_id:
            target = NotificationTarget(type=TargetType.LISTING, id=parsed.reference_id)

        drafts.append(
            NotificationDraft(
                recipient_id=parsed.recipient_id,
                type=ntype,
                target=target,
            )
        )

    return drafts
