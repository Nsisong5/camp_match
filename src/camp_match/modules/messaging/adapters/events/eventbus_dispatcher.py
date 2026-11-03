from __future__ import annotations

from typing import TYPE_CHECKING, Any

from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from camp_match.shared_kernel.application.event_bus import EventBus


class EventBusMessageEventDispatcher:
    def __init__(self, session_factory: Any, event_bus: EventBus) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus

    async def dispatch(self, event_id: EntityId) -> None:
        from camp_match.modules.messaging.adapters.persistence.outbox_repository import (
            SqlAlchemyOutboxRepository,
        )

        if hasattr(self._session_factory, "__aenter__"):
            outbox_repo = SqlAlchemyOutboxRepository(self._session_factory)
            event = await outbox_repo.get(event_id)
            if event:
                await self._event_bus.publish(event)
        else:
            async with self._session_factory() as session:
                outbox_repo = SqlAlchemyOutboxRepository(session)
                event = await outbox_repo.get(event_id)
                if event:
                    await self._event_bus.publish(event)
