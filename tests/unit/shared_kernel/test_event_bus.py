from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from camp_match.platform.in_memory_event_bus import InMemoryEventBus
from camp_match.shared_kernel.application.event_bus import publish_best_effort
from camp_match.shared_kernel.domain.events import DomainEvent


@dataclass(frozen=True)
class DummyEvent(DomainEvent):
    message: str = ""


@dataclass(frozen=True)
class UnsubscribedEvent(DomainEvent):
    pass


@pytest.mark.asyncio
@pytest.mark.unit
async def test_event_bus_publish_and_subscribe():
    bus = InMemoryEventBus()
    received_events: list[DummyEvent] = []

    async def handler(event: DomainEvent) -> None:
        if isinstance(event, DummyEvent):
            received_events.append(event)

    bus.subscribe(DummyEvent, handler)

    event = DummyEvent(message="hello")
    await bus.publish(event)

    assert len(received_events) == 1
    assert received_events[0] == event
    assert received_events[0].message == "hello"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_event_bus_unsubscribed_event():
    bus = InMemoryEventBus()
    received_events: list[DummyEvent] = []

    async def handler(event: DomainEvent) -> None:
        if isinstance(event, DummyEvent):
            received_events.append(event)

    bus.subscribe(DummyEvent, handler)

    event = UnsubscribedEvent()
    await bus.publish(event)

    assert len(received_events) == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_event_bus_multiple_handlers():
    bus = InMemoryEventBus()
    logs: list[str] = []

    async def handler_one(event: DomainEvent) -> None:
        logs.append("handler_one")

    async def handler_two(event: DomainEvent) -> None:
        logs.append("handler_two")

    bus.subscribe(DummyEvent, handler_one)
    bus.subscribe(DummyEvent, handler_two)

    event = DummyEvent()
    await bus.publish(event)

    assert "handler_one" in logs
    assert "handler_two" in logs
    assert len(logs) == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_publish_best_effort_swallows_exception():
    bus = AsyncMock()
    bus.publish.side_effect = RuntimeError("Publish failed")
    mock_logger = MagicMock()

    event = DummyEvent(message="test")
    await publish_best_effort(bus, event, log=mock_logger)

    mock_logger.warning.assert_called_once()
    call_args = mock_logger.warning.call_args
    assert call_args[0][0] == "event_publish_failed"
    assert call_args[1]["event_type"] == "DummyEvent"
    assert call_args[1]["event_id"] == str(event.event_id)
