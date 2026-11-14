from __future__ import annotations

from typing import TYPE_CHECKING, Any

from camp_match.modules.messaging.adapters.realtime.in_memory_gateway import InMemoryRealtimeGateway
from camp_match.modules.messaging.adapters.realtime.postgres_notify_gateway import PostgresNotifyRealtimeGateway

if TYPE_CHECKING:
    from camp_match.config.settings import Settings
    from camp_match.modules.messaging.adapters.realtime.connection_manager import ConnectionManager
    from camp_match.modules.messaging.application.ports.outbound import RealtimeGateway


def create_realtime_gateway(settings: Settings, connection_manager: ConnectionManager, session_factory: Any = None) -> RealtimeGateway:
    if settings.messaging_realtime_backend == "in_memory":
        return InMemoryRealtimeGateway(connection_manager)
    elif settings.messaging_realtime_backend == "postgres_notify":
        if not session_factory:
            raise RuntimeError("Session factory required for postgres_notify realtime backend.")
        return PostgresNotifyRealtimeGateway(session_factory)
    raise ValueError(f"Unsupported realtime backend: {settings.messaging_realtime_backend}")
