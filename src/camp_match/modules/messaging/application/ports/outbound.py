from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from camp_match.modules.messaging.domain.entities import (
    Conversation,
    ConversationParticipant,
    Message,
)
from camp_match.modules.messaging.domain.events import MessageCreated
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, slots=True)
class RestrictionDecision:
    allowed: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0


@dataclass(frozen=True, slots=True)
class ListingContext:
    provider_id: EntityId
    status: str


@dataclass(frozen=True, slots=True)
class BookingContext:
    student_id: EntityId
    property_id: EntityId
    listing_id: EntityId | None
    status: str


@dataclass(frozen=True, slots=True)
class ParticipantDisplay:
    profile_id: EntityId | None
    display_name: str | None
    profile_type: str | None


class ConversationRepository(Protocol):
    async def add(self, conversation: Conversation) -> bool:
        ...

    async def get_by_id(self, conversation_id: EntityId) -> Conversation | None:
        ...

    async def get_by_dedupe_key(self, dedupe_key: str) -> Conversation | None:
        ...

    async def list_for_participant(self, user_id: EntityId, page_request: PageRequest) -> Page[Conversation]:
        ...

    async def get_participant(self, conversation_id: EntityId, user_id: EntityId) -> ConversationParticipant | None:
        ...


class MessageRepository(Protocol):
    async def next_sequence(self, conversation_id: EntityId, message_created_at: datetime) -> int:
        ...

    async def add(self, message: Message) -> None:
        ...

    async def get_by_client_message_id(self, sender_id: EntityId, client_message_id: str) -> Message | None:
        ...

    async def get_in_conversation(self, conversation_id: EntityId, message_id: EntityId) -> Message | None:
        ...

    async def list_tail(self, conversation_id: EntityId, limit: int) -> list[Message]:
        ...

    async def list_before(self, conversation_id: EntityId, sequence: int, limit: int) -> list[Message]:
        ...

    async def list_after(self, conversation_id: EntityId, sequence: int, limit: int) -> list[Message]:
        ...

    async def last_messages(self, conversation_ids: list[EntityId]) -> dict[EntityId, Message]:
        ...

    async def unread_counts(self, user_id: EntityId, conversation_ids: list[EntityId]) -> dict[EntityId, int]:
        ...

    async def advance_read_position(
        self,
        conversation_id: EntityId,
        user_id: EntityId,
        sequence: int,
        message_id: EntityId,
        at: datetime,
    ) -> bool:
        ...


class OutboxRepository(Protocol):
    async def add(self, event: MessageCreated) -> None:
        ...

    async def get(self, event_id: EntityId) -> MessageCreated | None:
        ...

    async def claim_pending(self, limit: int) -> list[MessageCreated]:
        ...

    async def mark_dispatched(self, event_id: EntityId, at: datetime) -> None:
        ...

    async def record_failure(self, event_id: EntityId, error_class_name: str) -> None:
        ...


class ListingProvider(Protocol):
    async def get_listing_context(self, listing_id: EntityId) -> ListingContext | None:
        ...

    async def get_property_owner(self, property_id: EntityId) -> EntityId | None:
        ...


class BookingProvider(Protocol):
    async def get_booking_context(self, booking_id: EntityId, requester_id: EntityId) -> BookingContext | None:
        ...


class ProfileProvider(Protocol):
    async def get_display_info(self, identity_id: EntityId) -> ParticipantDisplay | None:
        ...


class CommunicationRestrictionProvider(Protocol):
    async def check(self, actor_id: EntityId, counterpart_id: EntityId | None = None) -> RestrictionDecision:
        ...


class RealtimeGateway(Protocol):
    async def push(self, user_ids: list[EntityId], event: object) -> None:
        ...


class MessageEventDispatcher(Protocol):
    async def dispatch(self, event_id: EntityId) -> None:
        ...


class RateLimiter(Protocol):
    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        ...


class AuthorizationService(Protocol):
    async def authorize(
        self,
        identity_id: EntityId,
        permission: Permission,
        resource_owner_id: EntityId | None = None,
    ) -> None:
        ...
