from __future__ import annotations

from typing import Any

from camp_match.modules.messaging.adapters.events.eventbus_dispatcher import (
    EventBusMessageEventDispatcher,
)
from camp_match.modules.messaging.application.use_cases.dispatch_outbox_events import (
    DispatchOutboxEvents,
)


def build_messaging_outbox_relay_job(
    session_factory: Any,
    session: Any,
    clock: Any,
    settings: Any,
    event_bus: Any,
) -> Any:
    dispatcher = EventBusMessageEventDispatcher(session_factory, event_bus)
    use_case = DispatchOutboxEvents(session_factory, dispatcher, clock)

    async def run() -> None:
        await use_case.execute(settings.messaging_outbox_batch_size)

    return run
