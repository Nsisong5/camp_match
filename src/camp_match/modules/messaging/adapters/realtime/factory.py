from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.messaging.adapters.realtime.in_memory_gateway import InMemoryRealtimeGateway

if TYPE_CHECKING:
    from camp_match.config.settings import Settings
    from camp_match.modules.messaging.adapters.realtime.connection_manager import ConnectionManager
    from camp_match.modules.messaging.application.ports.outbound import RealtimeGateway


def create_realtime_gateway(settings: Settings, connection_manager: ConnectionManager) -> RealtimeGateway:
    if settings.messaging_realtime_backend == "in_memory":
        return InMemoryRealtimeGateway(connection_manager)
    raise ValueError(f"Unsupported realtime backend: {settings.messaging_realtime_backend}")
