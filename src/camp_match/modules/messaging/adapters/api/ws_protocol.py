from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class BaseWSMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuthCommand(BaseWSMessage):
    type: Literal["auth"]
    token: str


class SubscribeCommand(BaseWSMessage):
    type: Literal["conversation.subscribe"]
    conversation_id: str


class UnsubscribeCommand(BaseWSMessage):
    type: Literal["conversation.unsubscribe"]
    conversation_id: str


class SendMessageCommand(BaseWSMessage):
    type: Literal["message.send"]
    conversation_id: str
    client_message_id: str
    content: str


class ReadAdvanceCommand(BaseWSMessage):
    type: Literal["read.advance"]
    conversation_id: str
    up_to_message_id: str


class PingCommand(BaseWSMessage):
    type: Literal["ping"]


def parse_client_command(data: dict[str, Any]) -> BaseModel:
    cmd_type = data.get("type")
    if cmd_type == "auth":
        return AuthCommand.model_validate(data)
    elif cmd_type == "conversation.subscribe":
        return SubscribeCommand.model_validate(data)
    elif cmd_type == "conversation.unsubscribe":
        return UnsubscribeCommand.model_validate(data)
    elif cmd_type == "message.send":
        return SendMessageCommand.model_validate(data)
    elif cmd_type == "read.advance":
        return ReadAdvanceCommand.model_validate(data)
    elif cmd_type == "ping":
        return PingCommand.model_validate(data)
    raise ValueError(f"Unknown command type: {cmd_type}")


# Server frame builders
def frame_auth_ok() -> dict[str, Any]:
    return {"type": "auth.ok"}


def frame_auth_expired() -> dict[str, Any]:
    return {"type": "auth.expired"}


def frame_subscribed(conversation_id: str) -> dict[str, Any]:
    return {"type": "subscribed", "conversation_id": conversation_id}


def frame_unsubscribed(conversation_id: str) -> dict[str, Any]:
    return {"type": "unsubscribed", "conversation_id": conversation_id}


def frame_message_created(event_id: str, message_payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": "message.created", "event_id": event_id, "message": message_payload}


def frame_message_accepted(request_id: str, message_payload: dict[str, Any], replayed: bool) -> dict[str, Any]:
    return {"type": "message.accepted", "request_id": request_id, "message": message_payload, "replayed": replayed}


def frame_read_accepted(conversation_id: str, last_read_message_id: str | None, unread_count: int) -> dict[str, Any]:
    return {
        "type": "read.accepted",
        "conversation_id": conversation_id,
        "last_read_message_id": last_read_message_id,
        "unread_count": unread_count,
    }


def frame_pong() -> dict[str, Any]:
    return {"type": "pong"}


def frame_error(code: str, message: str) -> dict[str, Any]:
    return {"type": "error", "error": {"code": code, "message": message}}
