from __future__ import annotations

from dataclasses import dataclass

from camp_match.modules.trust_safety.domain.value_objects import SafetyUpdateKind
from camp_match.shared_kernel.domain.events import DomainEvent
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, kw_only=True)
class SafetyUpdatePublished(DomainEvent):
    recipient_id: EntityId
    kind: SafetyUpdateKind
    reference_type: str | None = None
    reference_id: EntityId | None = None
