from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import pytest
from sqlalchemy import select

from camp_match.config.settings import get_settings
from camp_match.modules.platform_runtime.adapters.persistence.models import PlatformOutboxModel
from camp_match.modules.platform_runtime.adapters.persistence.outbox_repository import (
    SqlAlchemyOutboxRepository,
)
from camp_match.modules.platform_runtime.adapters.registry.event_contract_registry import (
    EventContractRegistry,
)
from camp_match.modules.platform_runtime.application.use_cases.relay_outbox_batch import (
    RelayOutboxBatchUseCase,
)
from camp_match.shared_kernel.domain.events import DomainEvent, EventContract
from camp_match.shared_kernel.domain.identifiers import EntityId
from camp_match.platform.in_memory_event_bus import InMemoryEventBus
from tests.support.fixed_clock import FixedClock


@dataclass(frozen=True, kw_only=True)
class RelayTestEvent(DomainEvent):
    msg: str


@pytest.mark.asyncio
async def test_relay_outbox_delivery_success(clear_db, session_factory) -> None:
    settings = get_settings()
    clock = FixedClock(datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC))
    event_bus = InMemoryEventBus()
    registry = EventContractRegistry()

    contract = EventContract(
        event_type="relay.test",
        event_class=RelayTestEvent,
        to_payload=lambda ev: {"msg": getattr(ev, "msg")},
        from_payload=lambda pl, eid, occ: RelayTestEvent(
            event_id=eid, occurred_at=occ, msg=pl["msg"]
        ),
    )
    registry.register(contract)

    published_events = []
    event_bus.subscribe(RelayTestEvent, lambda ev: published_events.append(ev))

    # Insert pending event directly via session
    async with session_factory() as session:
        ev_id = EntityId.new()
        session.add(
            PlatformOutboxModel(
                event_id=ev_id.value,
                event_type="relay.test",
                payload={"msg": "success test"},
                occurred_at=clock.now(),
                created_at=clock.now(),
                status="PENDING",
                attempts=0,
                next_attempt_at=clock.now(),
            )
        )
        await session.commit()

    use_case = RelayOutboxBatchUseCase(
        session_factory,
        SqlAlchemyOutboxRepository,
        registry,
        event_bus,
        clock,
        settings,
    )
    result = await use_case.execute(10)

    assert result.claimed == 1
    assert result.delivered == 1
    assert len(published_events) == 1
    assert published_events[0].msg == "success test"

    # Verify DB status is DELIVERED
    async with session_factory() as session:
        row = (await session.execute(
            select(PlatformOutboxModel).where(PlatformOutboxModel.event_id == ev_id.value)
        )).scalar_one()
        assert row.status == "DELIVERED"
        assert row.delivered_at is not None


@pytest.mark.asyncio
async def test_relay_outbox_failure_and_dead(clear_db, session_factory) -> None:
    settings = get_settings()
    clock = FixedClock(datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC))
    event_bus = InMemoryEventBus()
    registry = EventContractRegistry()  # empty registry -> unknown event type

    async with session_factory() as session:
        ev_id = EntityId.new()
        session.add(
            PlatformOutboxModel(
                event_id=ev_id.value,
                event_type="unknown.event",
                payload={"foo": "bar"},
                occurred_at=clock.now(),
                created_at=clock.now(),
                status="PENDING",
                attempts=settings.platform_outbox_max_attempts - 1,  # 1 attempt away from DEAD
                next_attempt_at=clock.now(),
            )
        )
        await session.commit()

    use_case = RelayOutboxBatchUseCase(
        session_factory,
        SqlAlchemyOutboxRepository,
        registry,
        event_bus,
        clock,
        settings,
    )
    result = await use_case.execute(10)

    assert result.claimed == 1
    assert result.dead == 1

    async with session_factory() as session:
        row = (await session.execute(
            select(PlatformOutboxModel).where(PlatformOutboxModel.event_id == ev_id.value)
        )).scalar_one()
        assert row.status == "DEAD"
        assert row.attempts == settings.platform_outbox_max_attempts
        assert row.last_error is not None
