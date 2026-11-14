"""Booking domain events."""
from __future__ import annotations

from dataclasses import dataclass

from camp_match.shared_kernel.domain.events import DomainEvent
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, kw_only=True)
class BookingCreated(DomainEvent):
    booking_id: EntityId
    student_id: EntityId
    property_id: EntityId
    listing_id: EntityId


@dataclass(frozen=True, kw_only=True)
class BookingConfirmed(DomainEvent):
    booking_id: EntityId
    student_id: EntityId
    property_id: EntityId
    listing_id: EntityId


@dataclass(frozen=True, kw_only=True)
class BookingCancelled(DomainEvent):
    booking_id: EntityId
    student_id: EntityId
    property_id: EntityId
    listing_id: EntityId
    cancelled_by: EntityId


@dataclass(frozen=True, kw_only=True)
class BookingExpired(DomainEvent):
    booking_id: EntityId
    student_id: EntityId
    property_id: EntityId
    listing_id: EntityId


@dataclass(frozen=True, kw_only=True)
class BookingInvalidated(DomainEvent):
    booking_id: EntityId
    student_id: EntityId
    property_id: EntityId
    listing_id: EntityId
    reason_code: str
    was_confirmed: bool


@dataclass(frozen=True, kw_only=True)
class HandoverOffered(DomainEvent):
    booking_id: EntityId
    student_id: EntityId
    property_id: EntityId
    listing_id: EntityId
    offered_by: EntityId


@dataclass(frozen=True, kw_only=True)
class HandoverAccepted(DomainEvent):
    booking_id: EntityId
    student_id: EntityId
    property_id: EntityId
    listing_id: EntityId


@dataclass(frozen=True, kw_only=True)
class BookingReminderDue(DomainEvent):
    booking_id: EntityId
    student_id: EntityId
    property_id: EntityId
    listing_id: EntityId
    reminder_type: str
