from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    event_id: EntityId = field(default_factory=EntityId.new)
    occurred_at: datetime | None = None


@dataclass(frozen=True)
class EventContract:
    event_type: str
    event_class: type[DomainEvent]
    to_payload: Callable[[DomainEvent], dict[str, Any]]
    from_payload: Callable[[dict[str, Any], EntityId, datetime | None], DomainEvent]

