from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from camp_match.modules.messaging.application.errors import DuplicateClientMessageId
from camp_match.modules.messaging.application.ports.outbound import (
    BookingContext,
    ListingContext,
    ParticipantDisplay,
    RateLimitResult,
    RestrictionDecision,
)
from camp_match.modules.messaging.domain.entities import (
    Conversation,
    ConversationParticipant,
    Message,
)
from camp_match.modules.messaging.domain.events import MessageCreated
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class FakeConversationRepository:
    def __init__(self, add_returns: bool = True) -> None:
        self.conversations: dict[str, Conversation] = {}  # id -> Conversation
        self.participants: dict[str, ConversationParticipant] = {}  # f"{conv_id}:{user_id}" -> ConversationParticipant
        self.add_returns = add_returns
        self.add_call_count = 0

    async def add(self, conversation: Conversation) -> bool:
        self.add_call_count += 1
        if not self.add_returns:
            return False
        if conversation.dedupe_key in [c.dedupe_key for c in self.conversations.values()]:
            return False
        self.conversations[str(conversation.id)] = conversation
        for pid in conversation.participant_ids:
            key = f"{conversation.id}:{pid}"
            self.participants[key] = ConversationParticipant(
                conversation_id=conversation.id,
                user_id=pid,
                joined_at=conversation.created_at or datetime.now(UTC),
                last_read_sequence=0,
                last_read_message_id=None,
                last_read_at=None,
            )
        return True

    async def get_by_id(self, conversation_id: EntityId) -> Conversation | None:
        return self.conversations.get(str(conversation_id))

    async def get_by_dedupe_key(self, dedupe_key: str) -> Conversation | None:
        for c in self.conversations.values():
            if c.dedupe_key == dedupe_key:
                return c
        return None

    async def list_for_participant(self, user_id: EntityId, page_request: PageRequest) -> Page[Conversation]:
        user_convs = []
        for c in self.conversations.values():
            if user_id in c.participant_ids:
                user_convs.append(c)
        
        user_convs.sort(key=lambda x: (x.last_activity_at or x.created_at, str(x.id)), reverse=True)

        total = len(user_convs)
        offset = (page_request.page - 1) * page_request.page_size
        page_items = user_convs[offset : offset + page_request.page_size]

        return Page(items=page_items, total=total, page=page_request.page, page_size=page_request.page_size)

    async def get_participant(self, conversation_id: EntityId, user_id: EntityId) -> ConversationParticipant | None:
        key = f"{conversation_id}:{user_id}"
        return self.participants.get(key)


class FakeMessageRepository:
    def __init__(self, conversation_repo: FakeConversationRepository | None = None) -> None:
        self.messages: list[Message] = []
        self.sequences: dict[str, int] = {}  # conv_id -> last_sequence
        self.conversation_repo = conversation_repo

    async def next_sequence(self, conversation_id: EntityId, message_created_at: datetime) -> int:
        cid_str = str(conversation_id)
        current = self.sequences.get(cid_str, 0)
        new_seq = current + 1
        self.sequences[cid_str] = new_seq
        return new_seq

    async def add(self, message: Message) -> None:
        for m in self.messages:
            if m.sender_id == message.sender_id and m.client_message_id.value == message.client_message_id.value:
                raise DuplicateClientMessageId("Duplicate client message ID.")
            if m.conversation_id == message.conversation_id and m.sequence == message.sequence:
                raise IntegrityError("Duplicate sequence in conversation.")
        self.messages.append(message)

    async def get_by_client_message_id(self, sender_id: EntityId, client_message_id: str) -> Message | None:
        for m in self.messages:
            if m.sender_id == sender_id and m.client_message_id.value == client_message_id:
                return m
        return None

    async def get_in_conversation(self, conversation_id: EntityId, message_id: EntityId) -> Message | None:
        for m in self.messages:
            if m.conversation_id == conversation_id and m.id == message_id:
                return m
        return None

    async def list_tail(self, conversation_id: EntityId, limit: int) -> list[Message]:
        conv_msgs = [m for m in self.messages if m.conversation_id == conversation_id]
        conv_msgs.sort(key=lambda x: x.sequence)
        return conv_msgs[-limit:]

    async def list_before(self, conversation_id: EntityId, sequence: int, limit: int) -> list[Message]:
        conv_msgs = [m for m in self.messages if m.conversation_id == conversation_id and m.sequence < sequence]
        conv_msgs.sort(key=lambda x: x.sequence)
        return conv_msgs[-limit:]

    async def list_after(self, conversation_id: EntityId, sequence: int, limit: int) -> list[Message]:
        conv_msgs = [m for m in self.messages if m.conversation_id == conversation_id and m.sequence > sequence]
        conv_msgs.sort(key=lambda x: x.sequence)
        return conv_msgs[:limit]

    async def last_messages(self, conversation_ids: list[EntityId]) -> dict[EntityId, Message]:
        result = {}
        for cid in conversation_ids:
            conv_msgs = [m for m in self.messages if m.conversation_id == cid]
            if conv_msgs:
                max_msg = max(conv_msgs, key=lambda x: x.sequence)
                result[cid] = max_msg
        return result

    async def unread_counts(self, user_id: EntityId, conversation_ids: list[EntityId]) -> dict[EntityId, int]:
        result = {}
        for cid in conversation_ids:
            last_read = 0
            if self.conversation_repo:
                part = await self.conversation_repo.get_participant(cid, user_id)
                if part:
                    last_read = part.last_read_sequence
            count = sum(1 for m in self.messages if m.conversation_id == cid and m.sender_id != user_id and m.sequence > last_read)
            result[cid] = count
        return result

    async def advance_read_position(
        self,
        conversation_id: EntityId,
        user_id: EntityId,
        sequence: int,
        message_id: EntityId,
        at: datetime,
    ) -> bool:
        if self.conversation_repo:
            key = f"{conversation_id}:{user_id}"
            part = self.conversation_repo.participants.get(key)
            if part and part.last_read_sequence < sequence:
                self.conversation_repo.participants[key] = ConversationParticipant(
                    conversation_id=part.conversation_id,
                    user_id=part.user_id,
                    joined_at=part.joined_at,
                    last_read_sequence=sequence,
                    last_read_message_id=message_id,
                    last_read_at=at,
                )
                return True
        return True


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.events: list[MessageCreated] = []

    async def add(self, event: MessageCreated) -> None:
        self.events.append(event)

    async def get(self, event_id: EntityId) -> MessageCreated | None:
        for e in self.events:
            if e.event_id == event_id:
                return e
        return None

    async def claim_pending(self, limit: int) -> list[MessageCreated]:
        return self.events[:limit]

    async def mark_dispatched(self, event_id: EntityId, at: datetime) -> None:
        pass

    async def record_failure(self, event_id: EntityId, error_class_name: str) -> None:
        pass


class FakeListingProvider:
    def __init__(self, listings: dict[str, tuple[EntityId, str]] | None = None, owners: dict[str, EntityId] | None = None) -> None:
        self.listings = listings or {}  # listing_id_str -> (provider_id, status)
        self.owners = owners or {}  # property_id_str -> owner_id

    async def get_listing_context(self, listing_id: EntityId) -> ListingContext | None:
        info = self.listings.get(str(listing_id))
        if not info:
            return None
        return ListingContext(provider_id=info[0], status=info[1])

    async def get_property_owner(self, property_id: EntityId) -> EntityId | None:
        return self.owners.get(str(property_id))


class FakeBookingProvider:
    def __init__(self, bookings: dict[str, Any] | None = None) -> None:
        self.bookings = bookings or {}  # booking_id_str -> booking object/dict

    async def get_booking_context(self, booking_id: EntityId, requester_id: EntityId) -> BookingContext | None:
        b = self.bookings.get(str(booking_id))
        if not b:
            return None
        if requester_id != b["student_id"] and requester_id != b["property_owner_id"]:
            return None
        return BookingContext(
            student_id=b["student_id"],
            property_id=b["property_id"],
            listing_id=b.get("listing_id"),
            status=b["status"],
        )


class FakeProfileProvider:
    def __init__(self, profiles: dict[str, ParticipantDisplay] | None = None, fail: bool = False) -> None:
        self.profiles = profiles or {}  # identity_id_str -> ParticipantDisplay
        self.fail = fail
        self.call_count = 0

    async def get_display_info(self, identity_id: EntityId) -> ParticipantDisplay | None:
        self.call_count += 1
        if self.fail:
            raise Exception("Profile provider failure")
        return self.profiles.get(str(identity_id))


class FakeRestrictionProvider:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed

    async def check(self, actor_id: EntityId, counterpart_id: EntityId | None = None) -> RestrictionDecision:
        return RestrictionDecision(allowed=self.allowed)


class FakeRateLimiter:
    def __init__(self, allowed: bool = True, retry_after: int = 30) -> None:
        self.allowed = allowed
        self.retry_after = retry_after

    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        if not self.allowed:
            return RateLimitResult(allowed=False, retry_after_seconds=self.retry_after)
        return RateLimitResult(allowed=True, retry_after_seconds=0)


class FakeAuthorizationService:
    def __init__(self, allow: bool = True) -> None:
        self.allow = allow

    async def authorize(self, identity_id: EntityId, permission: Any, resource_owner_id: EntityId | None = None) -> None:
        if not self.allow:
            from camp_match.shared_kernel.application.errors import ForbiddenError
            raise ForbiddenError("Forbidden")


class FakeUnitOfWork:
    def __init__(self, should_commit: bool = True) -> None:
        self.should_commit = should_commit
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            await self.rollback()
        elif self.should_commit and not self.rolled_back:
            await self.commit()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True
