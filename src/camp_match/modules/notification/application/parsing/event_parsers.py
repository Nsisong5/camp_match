"""Event parsers for Notification module."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from camp_match.modules.notification.domain.value_objects import (
    NotificationType,
    TargetType,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


def _to_uuid(val: Any) -> UUID:
    if isinstance(val, UUID):
        return val
    return UUID(str(val))


def parse_event(event_type: str, payload: dict[str, Any]) -> Any:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a dictionary.")

    if event_type == NotificationType.MESSAGE_NEW.value:
        return _parse_message_new(payload)
    elif event_type in {
        NotificationType.BOOKING_CREATED_PROVIDER.value,
        NotificationType.BOOKING_CONFIRMED_STUDENT.value,
        NotificationType.BOOKING_CONFIRMED_PROVIDER.value,
        NotificationType.BOOKING_EXPIRED_STUDENT.value,
    }:
        return _parse_booking_basic(payload)
    elif event_type in {
        NotificationType.BOOKING_CANCELLED_STUDENT.value,
        NotificationType.BOOKING_CANCELLED_PROVIDER.value,
    }:
        return _parse_booking_cancelled(payload)
    elif event_type in {
        NotificationType.VERIFICATION_VERIFIED.value,
        NotificationType.VERIFICATION_REJECTED.value,
        NotificationType.VERIFICATION_REVOKED.value,
    }:
        return _parse_verification(payload)
    elif event_type in {
        NotificationType.SAFETY_REPORT_RECEIVED.value,
        NotificationType.SAFETY_REPORT_REVIEWED.value,
        NotificationType.SAFETY_WARNING_ISSUED.value,
        NotificationType.SAFETY_COMMUNICATION_RESTRICTED.value,
        NotificationType.SAFETY_LISTING_SUSPENDED.value,
        NotificationType.SAFETY_RESTRICTION_LIFTED.value,
        "SafetyUpdatePublished",
    }:
        return _parse_safety_update(payload)
    else:
        raise ValueError(f"Unsupported event type: {event_type}")


class MessageNewEvent:
    def __init__(
        self,
        message_id: EntityId,
        conversation_id: EntityId,
        sender_id: EntityId,
        recipient_id: EntityId,
        sequence: int,
        context_type: str | None,
        message_created_at: str,
    ) -> None:
        self.message_id = message_id
        self.conversation_id = conversation_id
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.sequence = sequence
        self.context_type = context_type
        self.message_created_at = message_created_at


class BookingEventData:
    def __init__(
        self,
        booking_id: EntityId,
        student_id: EntityId,
        property_id: EntityId,
        listing_id: EntityId,
        cancelled_by: EntityId | None = None,
    ) -> None:
        self.booking_id = booking_id
        self.student_id = student_id
        self.property_id = property_id
        self.listing_id = listing_id
        self.cancelled_by = cancelled_by


class VerificationEventData:
    def __init__(
        self,
        case_id: EntityId,
        target_type: TargetType,
        target_id: EntityId,
        decision: str,
    ) -> None:
        self.case_id = case_id
        self.target_type = target_type
        self.target_id = target_id
        self.decision = decision


def _parse_message_new(p: dict[str, Any]) -> MessageNewEvent:
    for field in [
        "message_id",
        "conversation_id",
        "sender_id",
        "recipient_id",
        "sequence",
        "message_created_at",
    ]:
        if field not in p:
            raise ValueError(f"Missing required field: {field}")
    return MessageNewEvent(
        message_id=EntityId(_to_uuid(p["message_id"])),
        conversation_id=EntityId(_to_uuid(p["conversation_id"])),
        sender_id=EntityId(_to_uuid(p["sender_id"])),
        recipient_id=EntityId(_to_uuid(p["recipient_id"])),
        sequence=int(p["sequence"]),
        context_type=p.get("context_type"),
        message_created_at=str(p["message_created_at"]),
    )


def _parse_booking_basic(p: dict[str, Any]) -> BookingEventData:
    for field in ["booking_id", "student_id", "property_id", "listing_id"]:
        if field not in p:
            raise ValueError(f"Missing required field: {field}")
    return BookingEventData(
        booking_id=EntityId(_to_uuid(p["booking_id"])),
        student_id=EntityId(_to_uuid(p["student_id"])),
        property_id=EntityId(_to_uuid(p["property_id"])),
        listing_id=EntityId(_to_uuid(p["listing_id"])),
    )


def _parse_booking_cancelled(p: dict[str, Any]) -> BookingEventData:
    for field in [
        "booking_id",
        "student_id",
        "property_id",
        "listing_id",
        "cancelled_by",
    ]:
        if field not in p:
            raise ValueError(f"Missing required field: {field}")
    return BookingEventData(
        booking_id=EntityId(_to_uuid(p["booking_id"])),
        student_id=EntityId(_to_uuid(p["student_id"])),
        property_id=EntityId(_to_uuid(p["property_id"])),
        listing_id=EntityId(_to_uuid(p["listing_id"])),
        cancelled_by=EntityId(_to_uuid(p["cancelled_by"])),
    )


def _parse_verification(p: dict[str, Any]) -> VerificationEventData:
    for field in ["case_id", "target_type", "target_id", "decision"]:
        if field not in p:
            raise ValueError(f"Missing required field: {field}")
    tt_str = str(p["target_type"]).upper()
    if tt_str not in {"PROVIDER", "PROPERTY"}:
        raise ValueError(f"Invalid target_type: {tt_str}")

    decision_str = str(p["decision"]).upper()
    if decision_str not in {"VERIFIED", "REJECTED", "REVOKED"}:
        raise ValueError(f"Invalid decision: {decision_str}")

    return VerificationEventData(
        case_id=EntityId(_to_uuid(p["case_id"])),
        target_type=TargetType.VERIFICATION_CASE
        if tt_str == "PROPERTY"
        else TargetType.CONVERSATION,
        target_id=EntityId(_to_uuid(p["target_id"])),
        decision=decision_str,
    )


class SafetyUpdateEventData:
    def __init__(
        self,
        recipient_id: EntityId,
        kind: str,
        reference_type: str | None = None,
        reference_id: EntityId | None = None,
    ) -> None:
        self.recipient_id = recipient_id
        self.kind = kind
        self.reference_type = reference_type
        self.reference_id = reference_id


def _parse_safety_update(p: dict[str, Any]) -> SafetyUpdateEventData:
    for field in ["recipient_id", "kind"]:
        if field not in p:
            raise ValueError(f"Missing required field: {field}")
    kind_str = str(p["kind"]).upper()
    valid_kinds = {
        "REPORT_RECEIVED",
        "REPORT_REVIEWED",
        "WARNING_ISSUED",
        "COMMUNICATION_RESTRICTED",
        "LISTING_SUSPENDED",
        "RESTRICTION_LIFTED",
    }
    if kind_str not in valid_kinds:
        raise ValueError(f"Invalid safety update kind: {kind_str}")

    ref_id = p.get("reference_id")
    return SafetyUpdateEventData(
        recipient_id=EntityId(_to_uuid(p["recipient_id"])),
        kind=kind_str,
        reference_type=p.get("reference_type"),
        reference_id=EntityId(_to_uuid(ref_id)) if ref_id else None,
    )
