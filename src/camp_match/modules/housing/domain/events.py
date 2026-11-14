from __future__ import annotations

from dataclasses import dataclass

from camp_match.shared_kernel.domain.events import DomainEvent
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, kw_only=True)
class ListingSuspended(DomainEvent):
    listing_id: EntityId
    property_id: EntityId
    owner_id: EntityId
    reason_code: str
    reference_id: EntityId | None = None


@dataclass(frozen=True, kw_only=True)
class ListingSuspensionLifted(DomainEvent):
    listing_id: EntityId
    property_id: EntityId
    owner_id: EntityId
