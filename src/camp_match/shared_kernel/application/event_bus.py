"""Shared kernel event bus definition and publish helper."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

import structlog

from camp_match.shared_kernel.domain.events import DomainEvent

EventHandler = Callable[[DomainEvent], Awaitable[None]]

logger = structlog.get_logger()


class EventBus(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None: ...


class NoOpEventBus:
    async def publish(self, event: DomainEvent) -> None:
        pass

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        pass


async def publish_best_effort(
    event_bus: EventBus,
    event: DomainEvent,
    log: structlog.stdlib.BoundLogger | None = None,
) -> None:
    logger_to_use = log or logger
    try:
        await event_bus.publish(event)
    except Exception:
        ev_id = getattr(event, "event_id", getattr(event, "id", "unknown"))
        event_id_str = str(ev_id.value) if hasattr(ev_id, "value") else str(ev_id)
        event_type = type(event).__name__
        logger_to_use.warning(
            "event_publish_failed",
            event_type=event_type,
            event_id=event_id_str,
        )
