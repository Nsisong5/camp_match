from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from camp_match.modules.messaging.domain.entities import Conversation
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, slots=True)
class ParticipantView:
    user_id: EntityId
    profile_id: EntityId | None = None
    display_name: str | None = None
    profile_type: str | None = None


@dataclass(frozen=True, slots=True)
class LastMessageView:
    id: EntityId
    sender_id: EntityId
    preview: str
    sequence: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MessageView:
    id: EntityId
    conversation_id: EntityId
    sender_id: EntityId
    content: str
    sequence: int
    cursor: str
    created_at: datetime
    client_message_id: str | None = None


@dataclass(frozen=True, slots=True)
class ConversationView:
    id: EntityId
    context_type: str
    listing_id: EntityId | None
    booking_id: EntityId | None
    counterpart: ParticipantView
    last_message: LastMessageView | None
    last_activity_at: datetime | None
    unread_count: int
    last_read_message_id: EntityId | None
    created_at: datetime | None


@dataclass(frozen=True, slots=True)
class FindOrCreateResult:
    conversation: ConversationView
    created: bool


@dataclass(frozen=True, slots=True)
class SendMessageResult:
    message: MessageView
    replayed: bool


@dataclass(frozen=True, slots=True)
class HistoryPage:
    items: list[MessageView]
    has_older: bool
    has_newer: bool
    older_cursor: str | None
    newer_cursor: str | None


@dataclass(frozen=True, slots=True)
class ReadResult:
    conversation_id: EntityId
    last_read_message_id: EntityId | None
    unread_count: int


@dataclass(frozen=True, slots=True)
class RealtimeEvent:
    type: str  # e.g. "message.created"
    conversation_id: EntityId
    event_id: EntityId
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class FindOrCreateConversationRequest:
    actor_id: EntityId
    context_type: str
    listing_id: EntityId | None = None
    booking_id: EntityId | None = None


class FindOrCreateConversation(Protocol):
    async def execute(self, request: FindOrCreateConversationRequest) -> FindOrCreateResult:
        ...


@dataclass(frozen=True, slots=True)
class ListConversationsRequest:
    actor_id: EntityId
    page: PageRequest


class ListConversations(Protocol):
    async def execute(self, request: ListConversationsRequest) -> Page[ConversationView]:
        ...


@dataclass(frozen=True, slots=True)
class GetConversationRequest:
    actor_id: EntityId
    conversation_id: EntityId


class GetConversation(Protocol):
    async def execute(self, request: GetConversationRequest) -> ConversationView:
        ...


@dataclass(frozen=True, slots=True)
class SendMessageRequest:
    actor_id: EntityId
    conversation_id: EntityId
    client_message_id: str
    content: str


class SendMessage(Protocol):
    async def execute(self, request: SendMessageRequest) -> SendMessageResult:
        ...


@dataclass(frozen=True, slots=True)
class GetMessageHistoryRequest:
    actor_id: EntityId
    conversation_id: EntityId
    limit: int = 30
    before: str | None = None
    after: str | None = None


class GetMessageHistory(Protocol):
    async def execute(self, request: GetMessageHistoryRequest) -> HistoryPage:
        ...


@dataclass(frozen=True, slots=True)
class MarkConversationReadRequest:
    actor_id: EntityId
    conversation_id: EntityId
    up_to_message_id: EntityId


class MarkConversationRead(Protocol):
    async def execute(self, request: MarkConversationReadRequest) -> ReadResult:
        ...


@dataclass(frozen=True, slots=True)
class AuthorizeConnectionRequest:
    actor_id: EntityId


class AuthorizeConnection(Protocol):
    async def execute(self, request: AuthorizeConnectionRequest) -> None:
        ...


@dataclass(frozen=True, slots=True)
class AuthorizeSubscriptionRequest:
    actor_id: EntityId
    conversation_id: EntityId


class AuthorizeSubscription(Protocol):
    async def execute(self, request: AuthorizeSubscriptionRequest) -> Conversation:
        ...


@dataclass(frozen=True, slots=True)
class DispatchOutboxEventsRequest:
    limit: int = 50


class DispatchOutboxEvents(Protocol):
    async def execute(self, request: DispatchOutboxEventsRequest) -> int:
        ...


@dataclass(frozen=True, slots=True)
class RestrictCommunicationRequest:
    actor_id: EntityId
    user_id: EntityId
    ends_at: datetime
    source_reference: EntityId


class RestrictCommunication(Protocol):
    async def execute(self, request: RestrictCommunicationRequest) -> None:
        ...


@dataclass(frozen=True, slots=True)
class LiftCommunicationRestrictionRequest:
    actor_id: EntityId
    source_reference: EntityId


class LiftCommunicationRestriction(Protocol):
    async def execute(self, request: LiftCommunicationRestrictionRequest) -> None:
        ...


@dataclass(frozen=True, slots=True)
class GetMessageForParticipantRequest:
    actor_id: EntityId
    conversation_id: EntityId
    message_id: EntityId


class GetMessageForParticipant(Protocol):
    async def execute(self, request: GetMessageForParticipantRequest) -> Message:
        ...
