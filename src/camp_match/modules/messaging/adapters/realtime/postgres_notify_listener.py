from __future__ import annotations

import asyncio
import json
from typing import Any
import asyncpg
import structlog

from camp_match.modules.messaging.adapters.persistence.repository import (
    SqlAlchemyMessageRepository,
)
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


async def run_postgres_notify_listener(
    database_url: str,
    session_factory: Any,
    connection_manager: Any,
    settings: Any,
) -> None:
    dsn = database_url.replace("+asyncpg", "")
    backoff = 1.0

    while True:
        try:
            conn = await asyncpg.connect(dsn)
            backoff = 1.0
            logger.info("postgres_notify_listener_connected")

            await conn.add_listener(
                "camp_match_realtime",
                lambda connection, pid, channel, payload: asyncio.create_task(
                    _handle_notification(payload, session_factory, connection_manager)
                ),
            )

            while not conn.is_closed():
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info("postgres_notify_listener_cancelled")
            break
        except Exception as e:
            logger.warning("postgres_notify_listener_disconnected", error=str(e), backoff=backoff)
            await asyncio.sleep(backoff)
            backoff = min(60.0, backoff * 2)


async def _handle_notification(
    payload_str: str, session_factory: Any, connection_manager: Any
) -> None:
    try:
        data = json.loads(payload_str)
        kind = data.get("kind")
        conversation_id = data.get("conversation_id")
        message_id = data.get("message_id")
        user_ids = data.get("user_ids", [])

        if kind != "message.created" or not conversation_id or not message_id or not user_ids:
            return

        conv_id_obj = EntityId.from_string(conversation_id)
        msg_id_obj = EntityId.from_string(message_id)
        target_user_ids = [EntityId.from_string(uid) for uid in user_ids]

        async with session_factory() as session:
            msg_repo = SqlAlchemyMessageRepository(session)
            msg = await msg_repo.get(msg_id_obj)
            if not msg:
                return

            frame = {
                "type": "message.created",
                "event_id": str(msg.id),
                "message": msg.to_payload(),
            }

            for user_id in target_user_ids:
                await connection_manager.broadcast_to_subscribers([user_id], conv_id_obj.value, frame)

    except Exception as e:
        logger.error("postgres_notify_handle_error", error=str(e))
