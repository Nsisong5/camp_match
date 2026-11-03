from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from camp_match.shared_kernel.domain.events import DomainEvent
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, kw_only=True)
class MessageCreated(DomainEvent):
    message_id: EntityId
    conversation_id: EntityId
    sender_id: EntityId
    recipient_id: EntityId
    sequence: int
    context_type: str
    message_created_at: datetime

    def to_payload(self) -> dict[str, object]:
        return {
            "event_id": str(self.event_id),
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "message_id": str(self.message_id),
            "conversation_id": str(self.conversation_id),
            "sender_id": str(self.sender_id),
            "recipient_id": str(self.recipient_id),
            "sequence": self.sequence,
            "context_type": self.context_type,
            "message_created_at": self.message_created_at.isoformat(),
        }

    @classmethod
    def from_payload(cls, data: dict[str, object]) -> MessageCreated:
        occurred_at = (
            datetime.fromisoformat(str(data["occurred_at"]))
            if data.get("occurred_at")
            else None
        )
        message_created_at = datetime.fromisoformat(str(data["message_created_at"]))
        return cls(
            event_id=EntityId.from_string(str(data["event_id"])),
            occurred_at=occurred_at,
            message_id=EntityId.from_string(str(data["message_id"])),
            conversation_id=EntityId.from_string(str(data["conversation_id"])),
            sender_id=EntityId.from_string(str(data["sender_id"])),
            recipient_id=EntityId.from_string(str(data["recipient_id"])),
            sequence=int(str(data["sequence"])),
            context_type=str(data["context_type"]),
            message_created_at=message_created_at,
        )
