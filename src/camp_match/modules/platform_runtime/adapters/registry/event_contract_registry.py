from __future__ import annotations

from datetime import datetime
from typing import Any

from camp_match.modules.platform_runtime.domain.errors import (
    InvalidEventPayload,
    UnknownEventType,
)
from camp_match.shared_kernel.domain.events import DomainEvent, EventContract
from camp_match.shared_kernel.domain.identifiers import EntityId


class EventContractRegistry:
    def __init__(self) -> None:
        self._contracts_by_type: dict[str, EventContract] = {}
        self._contracts_by_class: dict[type[DomainEvent], EventContract] = {}

    def register(self, contract: EventContract) -> None:
        self._contracts_by_type[contract.event_type] = contract
        self._contracts_by_class[contract.event_class] = contract

    def to_payload(self, event: DomainEvent) -> tuple[str, dict[str, Any]]:
        contract = self._contracts_by_class.get(type(event))
        if not contract:
            raise UnknownEventType(type(event).__name__)
        try:
            payload = contract.to_payload(event)
        except Exception as e:
            raise InvalidEventPayload(
                f"Failed to serialize event payload: {e}"
            ) from e
        return contract.event_type, payload

    def from_payload(
        self,
        event_type: str,
        payload: dict[str, Any],
        event_id: EntityId,
        occurred_at: datetime | None,
    ) -> DomainEvent:
        contract = self._contracts_by_type.get(event_type)
        if not contract:
            raise UnknownEventType(event_type)
        try:
            return contract.from_payload(payload, event_id, occurred_at)
        except Exception as e:
            raise InvalidEventPayload(
                f"Failed to deserialize event payload for {event_type}: {e}"
            ) from e
