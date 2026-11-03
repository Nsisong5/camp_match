from __future__ import annotations

from fastapi import APIRouter, WebSocket

from camp_match.modules.messaging.adapters.api.ws_handler import handle_websocket

router = APIRouter()


@router.websocket("/api/v1/messaging/ws")
async def messaging_websocket_endpoint(websocket: WebSocket) -> None:
    connection_manager = websocket.app.state.connection_manager
    session_factory = websocket.app.state.db_session_factory
    rate_limiter = websocket.app.state.rate_limiter
    await handle_websocket(websocket, connection_manager, session_factory, rate_limiter)
