from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FindOrCreateConversationSchema(BaseSchema):
    context_type: str
    listing_id: UUID | None = None
    booking_id: UUID | None = None


class SendMessageSchema(BaseSchema):
    client_message_id: str
    content: str


class MarkReadSchema(BaseSchema):
    up_to_message_id: UUID


class ParticipantViewSchema(BaseSchema):
    user_id: UUID
    profile_id: UUID | None = None
    display_name: str | None = None
    profile_type: str | None = None


class LastMessageViewSchema(BaseSchema):
    id: UUID
    sender_id: UUID
    preview: str
    sequence: int
    created_at: datetime


class MessageViewSchema(BaseSchema):
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    content: str
    sequence: int
    cursor: str
    created_at: datetime
    client_message_id: str | None = None


class ConversationViewSchema(BaseSchema):
    id: UUID
    context_type: str
    listing_id: UUID | None = None
    booking_id: UUID | None = None
    counterpart: ParticipantViewSchema
    last_message: LastMessageViewSchema | None = None
    last_activity_at: datetime | None = None
    unread_count: int
    last_read_message_id: UUID | None = None
    created_at: datetime | None = None


class FindOrCreateResultSchema(BaseSchema):
    conversation: ConversationViewSchema
    created: bool


class SendMessageResultSchema(BaseSchema):
    message: MessageViewSchema
    replayed: bool


class HistoryPageSchema(BaseSchema):
    items: list[MessageViewSchema]
    has_older: bool
    has_newer: bool
    older_cursor: str | None = None
    newer_cursor: str | None = None


class ReadResultSchema(BaseSchema):
    conversation_id: UUID
    last_read_message_id: UUID | None = None
    unread_count: int


class PageSchema(BaseSchema, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
