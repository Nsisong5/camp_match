from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from camp_match.modules.messaging.domain.value_objects import (
    ClientMessageId,
    ConversationContext,
    MessageContent,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, slots=True)
class Conversation:
    id: EntityId
    context: ConversationContext
    participant_ids: tuple[EntityId, EntityId]
    dedupe_key: str
    last_sequence: int = 0
    last_activity_at: datetime | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.participant_ids, (tuple, list)) or len(self.participant_ids) != 2:
            raise ValueError("Conversation must have exactly two participants.")
        p1, p2 = self.participant_ids
        if p1 == p2:
            raise ValueError("Conversation participants must be distinct.")
        if not isinstance(self.last_sequence, int) or self.last_sequence < 0:
            raise ValueError("Last sequence must be a non-negative integer.")

    def counterpart_of(self, user_id: EntityId) -> EntityId:
        p1, p2 = self.participant_ids
        if user_id == p1:
            return p2
        if user_id == p2:
            return p1
        raise ValueError("User is not a participant in this conversation.")


@dataclass(frozen=True, slots=True)
class ConversationParticipant:
    conversation_id: EntityId
    user_id: EntityId
    joined_at: datetime
    last_read_sequence: int = 0
    last_read_message_id: EntityId | None = None
    last_read_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.last_read_sequence, int) or self.last_read_sequence < 0:
            raise ValueError("Last read sequence must be a non-negative integer.")


@dataclass(frozen=True, slots=True)
class Message:
    id: EntityId
    conversation_id: EntityId
    sender_id: EntityId
    sequence: int
    content: MessageContent
    client_message_id: ClientMessageId
    created_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.sequence, int) or self.sequence < 1:
            raise ValueError("Message sequence must be a positive integer.")


@dataclass(slots=True)
class CommunicationRestriction:
    id: EntityId
    user_id: EntityId
    starts_at: datetime
    ends_at: datetime
    source_reference: EntityId
    status: str = "ACTIVE"
    lifted_at: datetime | None = None
    created_at: datetime | None = None
