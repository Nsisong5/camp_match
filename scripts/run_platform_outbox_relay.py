#!/usr/bin/env python3
from __future__ import annotations

import asyncio

from camp_match.config.settings import get_settings
from camp_match.modules.platform_runtime.adapters.persistence.outbox_repository import (
    SqlAlchemyOutboxRepository,
)
from camp_match.modules.platform_runtime.adapters.registry.event_contract_registry import (
    EventContractRegistry,
)
from camp_match.modules.platform_runtime.application.use_cases.relay_outbox_batch import (
    RelayOutboxBatchUseCase,
)
from camp_match.platform.clock import get_clock
from camp_match.platform.db.session import create_engine, create_session_factory
from camp_match.platform.event_bus import build_event_bus


async def run_relay() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    clock = get_clock()
    event_bus = build_event_bus(session_factory, clock, settings)
    registry = EventContractRegistry()

    use_case = RelayOutboxBatchUseCase(
        session_factory,
        SqlAlchemyOutboxRepository,
        registry,
        event_bus,
        clock,
        settings,
    )
    result = await use_case.execute(settings.platform_outbox_batch_size)
    print(
        f"Platform Outbox Relay: claimed={result.claimed}, "
        f"delivered={result.delivered}, failed={result.failed}, dead={result.dead}"
    )

    await engine.dispose()


def main() -> None:
    asyncio.run(run_relay())


if __name__ == "__main__":
    main()
