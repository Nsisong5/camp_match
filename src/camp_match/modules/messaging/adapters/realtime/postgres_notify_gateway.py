from __future__ import annotations

import json
from typing import Any
import structlog
from sqlalchemy import text

logger = structlog.get_logger()


class PostgresNotifyRealtimeGateway:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def push(self, user_ids: list[Any], event: object) -> None:
        if not user_ids:
            return
        conv_id = getattr(event, "conversation_id", None)
        message_id = getattr(event, "message_id", getattr(event, "event_id", None))
        if not conv_id or not message_id:
            return

        u_ids = [str(uid.value if hasattr(uid, "value") else uid) for uid in user_ids]
        payload = json.dumps({
            "kind": "message.created",
            "conversation_id": str(conv_id.value if hasattr(conv_id, "value") else conv_id),
            "message_id": str(message_id.value if hasattr(message_id, "value") else message_id),
            "user_ids": u_ids,
        })

        try:
            async with self._session_factory() as session:
                await session.execute(
                    text("SELECT pg_notify('camp_match_realtime', :payload)"),
                    {"payload": payload},
                )
                await session.commit()
        except Exception as e:
            logger.warning("postgres_notify_push_failed", error=str(e))
