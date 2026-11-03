#!/usr/bin/env python3
from __future__ import annotations

import asyncio

from camp_match.config.settings import get_settings
from camp_match.modules.messaging.adapters.events.eventbus_dispatcher import (
    EventBusMessageEventDispatcher,
)
from camp_match.modules.messaging.application.use_cases.dispatch_outbox_events import (
    DispatchOutboxEvents,
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

    dispatcher = EventBusMessageEventDispatcher(session_factory, event_bus)

    use_case = DispatchOutboxEvents(session_factory, dispatcher, clock)
    result = await use_case.execute(settings.messaging_outbox_batch_size)
    print(f"Messaging Outbox Relay: claimed={result.claimed}, dispatched={result.dispatched}, failed={result.failed}")

    await engine.dispose()


def main() -> None:
    asyncio.run(run_relay())


if __name__ == "__main__":
    main()
