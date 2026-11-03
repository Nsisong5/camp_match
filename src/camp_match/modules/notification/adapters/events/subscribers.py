"""Event subscribers and payload conversion for Notification module."""
from __future__ import annotations

import importlib
from typing import Any

import structlog

from camp_match.modules.booking.domain.events import (
    BookingCancelled,
    BookingConfirmed,
    BookingCreated,
    BookingExpired,
)
from camp_match.modules.messaging.domain.events import MessageCreated
from camp_match.modules.notification.adapters.housing.property_owner_provider import (
    SqlAlchemyPropertyOwnerProvider,
)
from camp_match.modules.notification.adapters.persistence.inbox_repository import (
    SqlAlchemyInboxRepository,
)
from camp_match.modules.notification.adapters.persistence.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from camp_match.modules.notification.application.ports.inbound import (
    ProcessInboxEventRequest,
    ReceiveEventRequest,
)
from camp_match.modules.notification.application.use_cases.process_inbox_event import (
    ProcessInboxEventUseCase,
)
from camp_match.modules.notification.application.use_cases.receive_event import (
    ReceiveEventUseCase,
)
from camp_match.modules.verification.domain.events import VerificationDecisionRecorded
from camp_match.modules.trust_safety.application.ports.events import (
    SafetyUpdatePublished,
)
from camp_match.modules.notification.domain.value_objects import NotificationType
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork

logger = structlog.get_logger()


def event_to_payload(event: Any) -> tuple[str, str, dict[str, Any]]:
    event_id = str(event.event_id)
    payload: dict[str, Any] = {}

    if isinstance(event, MessageCreated):
        event_type = NotificationType.MESSAGE_NEW.value
        payload = {
            "message_id": str(event.message_id),
            "conversation_id": str(event.conversation_id),
            "sender_id": str(event.sender_id),
            "recipient_id": str(event.recipient_id),
            "sequence": event.sequence,
            "context_type": event.context_type,
            "message_created_at": (
                event.message_created_at.isoformat()
                if hasattr(event.message_created_at, "isoformat")
                else str(event.message_created_at)
            ),
        }
    elif isinstance(event, BookingCreated):
        event_type = NotificationType.BOOKING_CREATED_PROVIDER.value
        payload = {
            "booking_id": str(event.booking_id),
            "student_id": str(event.student_id),
            "property_id": str(event.property_id),
            "listing_id": str(event.listing_id),
        }
    elif isinstance(event, BookingConfirmed):
        event_type = NotificationType.BOOKING_CONFIRMED_STUDENT.value
        payload = {
            "booking_id": str(event.booking_id),
            "student_id": str(event.student_id),
            "property_id": str(event.property_id),
            "listing_id": str(event.listing_id),
        }
    elif isinstance(event, BookingExpired):
        event_type = NotificationType.BOOKING_EXPIRED_STUDENT.value
        payload = {
            "booking_id": str(event.booking_id),
            "student_id": str(event.student_id),
            "property_id": str(event.property_id),
            "listing_id": str(event.listing_id),
        }
    elif isinstance(event, BookingCancelled):
        event_type = NotificationType.BOOKING_CANCELLED_STUDENT.value
        payload = {
            "booking_id": str(event.booking_id),
            "student_id": str(event.student_id),
            "property_id": str(event.property_id),
            "listing_id": str(event.listing_id),
            "cancelled_by": str(event.cancelled_by),
        }
    elif isinstance(event, VerificationDecisionRecorded):
        decision_str = str(event.decision).upper()
        mapping = {
            "VERIFIED": NotificationType.VERIFICATION_VERIFIED.value,
            "REJECTED": NotificationType.VERIFICATION_REJECTED.value,
            "REVOKED": NotificationType.VERIFICATION_REVOKED.value,
        }
        event_type = mapping.get(decision_str, NotificationType.VERIFICATION_VERIFIED.value)
        payload = {
            "case_id": str(event.case_id),
            "target_type": (
                event.target_type.value
                if hasattr(event.target_type, "value")
                else str(event.target_type)
            ),
            "target_id": str(event.target_id),
            "decision": decision_str,
        }
    elif isinstance(event, SafetyUpdatePublished):
        kind_map = {
            "REPORT_RECEIVED": NotificationType.SAFETY_REPORT_RECEIVED.value,
            "REPORT_REVIEWED": NotificationType.SAFETY_REPORT_REVIEWED.value,
            "WARNING_ISSUED": NotificationType.SAFETY_WARNING_ISSUED.value,
            "COMMUNICATION_RESTRICTED": NotificationType.SAFETY_COMMUNICATION_RESTRICTED.value,
            "LISTING_SUSPENDED": NotificationType.SAFETY_LISTING_SUSPENDED.value,
            "RESTRICTION_LIFTED": NotificationType.SAFETY_RESTRICTION_LIFTED.value,
        }
        kind_str = event.kind.value if hasattr(event.kind, "value") else str(event.kind)
        event_type = kind_map.get(kind_str, NotificationType.SAFETY_WARNING_ISSUED.value)
        payload = {
            "recipient_id": str(event.recipient_id),
            "kind": kind_str,
            "reference_type": event.reference_type,
            "reference_id": str(event.reference_id) if event.reference_id else None,
        }
    else:
        raise ValueError(f"Unknown event type: {type(event)}")

    return event_id, event_type, payload


def create_handler(
    event_cls: Any,
    session_factory: Any,
    clock: Any,
    settings: Any,
    debug_fail: bool,
) -> Any:
    async def handler(event: object) -> None:
        event_id, event_type, payload = event_to_payload(event)

        async with session_factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            inbox_repo = SqlAlchemyInboxRepository(session)
            notification_repo = SqlAlchemyNotificationRepository(session)
            
            housing_repo_mod = importlib.import_module(
                "camp_match.modules.housing.adapters.persistence.repository"
            )
            property_repo = housing_repo_mod.SqlAlchemyPropertyRepository(session)
            property_owner_provider = SqlAlchemyPropertyOwnerProvider(property_repo)

            receive_uc = ReceiveEventUseCase(inbox_repo, uow, clock)
            inserted = await receive_uc.execute(
                ReceiveEventRequest(
                    event_id=event_id, event_type=event_type, payload=payload
                )
            )
            if inserted:
                process_uc = ProcessInboxEventUseCase(
                    inbox_repo=inbox_repo,
                    notification_repo=notification_repo,
                    property_owner_provider=property_owner_provider,
                    uow=uow,
                    clock=clock,
                    max_attempts=settings.notification_inbox_max_attempts,
                    backoff_base=settings.notification_inbox_backoff_base_seconds,
                    backoff_cap=settings.notification_inbox_backoff_cap_seconds,
                    debug_fail=debug_fail,
                )
                await process_uc.execute(
                    ProcessInboxEventRequest(event_id=event_id)
                )

    return handler
