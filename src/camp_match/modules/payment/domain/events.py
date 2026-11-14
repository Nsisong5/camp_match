"""Payment domain events."""
from __future__ import annotations

from dataclasses import dataclass

from camp_match.shared_kernel.domain.events import DomainEvent
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, kw_only=True)
class PaymentOutcomeRecorded(DomainEvent):
    payment_attempt_id: EntityId
    booking_id: EntityId
    student_id: EntityId
    property_id: EntityId
    listing_id: EntityId
    outcome: str
