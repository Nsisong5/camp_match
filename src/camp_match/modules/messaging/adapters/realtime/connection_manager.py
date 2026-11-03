from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()


@dataclass
class Connection:
    websocket: WebSocket
    user_id: UUID
    connection_id: UUID = field(default_factory=uuid4)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    subscriptions: set[UUID] = field(default_factory=set)
    authenticated_until: datetime | None = None


class ConnectionManager:
    def __init__(self, send_timeout_seconds: float = 5.0) -> None:
        self._send_timeout_seconds = send_timeout_seconds
        # user_id -> {connection_id -> Connection}
        self._user_connections: dict[UUID, dict[UUID, Connection]] = {}
        self._lock = asyncio.Lock()

    async def register(self, connection: Connection) -> None:
        async with self._lock:
            user_conns = self._user_connections.setdefault(connection.user_id, {})
            user_conns[connection.connection_id] = connection
        logger.info("ws_connection_registered", user_id=str(connection.user_id), connection_id=str(connection.connection_id))

    async def unregister(self, connection: Connection) -> None:
        async with self._lock:
            user_conns = self._user_connections.get(connection.user_id)
            if user_conns and connection.connection_id in user_conns:
                del user_conns[connection.connection_id]
                if not user_conns:
                    del self._user_connections[connection.user_id]
        logger.info("ws_connection_unregistered", user_id=str(connection.user_id), connection_id=str(connection.connection_id))

    async def subscribe(self, connection_id: UUID, conversation_id: UUID) -> bool:
        async with self._lock:
            for user_conns in self._user_connections.values():
                if connection_id in user_conns:
                    user_conns[connection_id].subscriptions.add(conversation_id)
                    return True
        return False

    async def unsubscribe(self, connection_id: UUID, conversation_id: UUID) -> bool:
        async with self._lock:
            for user_conns in self._user_connections.values():
                if connection_id in user_conns:
                    user_conns[connection_id].subscriptions.discard(conversation_id)
                    return True
        return False

    async def count_user_connections(self, user_id: UUID) -> int:
        async with self._lock:
            user_conns = self._user_connections.get(user_id)
            return len(user_conns) if user_conns else 0

    async def send(self, connection: Connection, frame: dict[str, Any]) -> None:
        async with connection.send_lock:
            try:
                async with asyncio.timeout(self._send_timeout_seconds):
                    await connection.websocket.send_json(frame)
            except Exception as e:
                logger.warning("ws_send_failed", connection_id=str(connection.connection_id), error=str(e))
                try:
                    await connection.websocket.close()
                except Exception:
                    pass
                await self.unregister(connection)

    async def broadcast_to_subscribers(self, user_ids: list[Any], conversation_id: Any, frame: dict[str, Any]) -> None:
        target_conns = []
        conv_uuid = conversation_id.value if hasattr(conversation_id, "value") else conversation_id
        async with self._lock:
            for uid in user_ids:
                uid_uuid = uid.value if hasattr(uid, "value") else uid
                user_conns = self._user_connections.get(uid_uuid)
                if user_conns:
                    for conn in user_conns.values():
                        if conv_uuid in conn.subscriptions:
                            target_conns.append(conn)

        for conn in target_conns:
            asyncio.create_task(self.send(conn, frame))

    async def close_all(self) -> None:
        async with self._lock:
            all_conns = [
                conn for user_conns in self._user_connections.values() for conn in user_conns.values()
            ]
            self._user_connections.clear()

        for conn in all_conns:
            try:
                await conn.websocket.close()
            except Exception:
                pass
