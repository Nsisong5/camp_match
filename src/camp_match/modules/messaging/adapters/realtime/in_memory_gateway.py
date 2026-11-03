from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from camp_match.modules.messaging.adapters.realtime.connection_manager import ConnectionManager
    from camp_match.shared_kernel.domain.identifiers import EntityId


class InMemoryRealtimeGateway:
    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._connection_manager = connection_manager

    async def push(self, user_ids: list[EntityId], event: object) -> None:
        # event is expected to be RealtimeEvent or MessageCreated/payload
        conv_id = getattr(event, "conversation_id", None)
        event_id = getattr(event, "event_id", None)
        payload = getattr(event, "payload", None)
        if hasattr(event, "to_payload") and callable(event.to_payload):
            payload = event.to_payload()

        if not conv_id or not event_id:
            return

        frame = {
            "type": "message.created",
            "event_id": str(event_id),
            "message": payload,
        }
        await self._connection_manager.broadcast_to_subscribers(user_ids, conv_id.value if hasattr(conv_id, "value") else conv_id, frame)
