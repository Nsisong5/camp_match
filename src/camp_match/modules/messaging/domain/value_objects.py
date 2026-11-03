from __future__ import annotations

import base64
import re
from dataclasses import dataclass

from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, slots=True)
class ConversationContext:
    type: str
    listing_id: EntityId | None = None
    booking_id: EntityId | None = None

    def __post_init__(self) -> None:
        if self.type not in ("LISTING", "BOOKING"):
            raise ValueError("Conversation context type must be 'LISTING' or 'BOOKING'.")
        
        if self.type == "LISTING":
            if not self.listing_id or self.booking_id:
                raise ValueError("LISTING context requires listing_id and no booking_id.")
        elif self.type == "BOOKING":
            if not self.booking_id or self.listing_id:
                raise ValueError("BOOKING context requires booking_id and no listing_id.")

    def dedupe_key(self, enquirer_id: EntityId) -> str:
        if self.type == "LISTING":
            return f"listing:{self.listing_id}:{enquirer_id}"
        elif self.type == "BOOKING":
            return f"booking:{self.booking_id}"
        raise ValueError(f"Unknown context type: {self.type}")


@dataclass(frozen=True, slots=True)
class MessageContent:
    value: str

    @classmethod
    def create(cls, raw: str, max_length: int = 2000) -> MessageContent:
        if not isinstance(raw, str):
            raise ValueError("Message content must be a string.")
        stripped = raw.strip()
        if not stripped:
            raise ValueError("Message content cannot be empty or whitespace-only.")
        if len(stripped) > max_length:
            raise ValueError(f"Message content exceeds maximum length of {max_length}.")
        return cls(value=stripped)


@dataclass(frozen=True, slots=True)
class ClientMessageId:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValueError("Client message ID must be a string.")
        if not (1 <= len(self.value) <= 64):
            raise ValueError("Client message ID must be between 1 and 64 characters.")
        if not re.match(r"^[A-Za-z0-9_-]+$", self.value):
            raise ValueError("Client message ID contains invalid characters.")


class SequenceCursor:
    @staticmethod
    def encode(sequence: int) -> str:
        if not isinstance(sequence, int) or sequence < 0:
            raise ValueError("Sequence must be a non-negative integer.")
        raw = f"s:{sequence}"
        encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).rstrip(b"=").decode("utf-8")
        return encoded

    @staticmethod
    def decode(raw: str) -> int:
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("Sequence cursor cannot be empty.")
        try:
            # Add padding back if necessary
            padding = "=" * (-len(raw) % 4)
            decoded_bytes = base64.urlsafe_b64decode((raw + padding).encode("utf-8"))
            decoded_str = decoded_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Invalid sequence cursor encoding: {e}") from e

        if not decoded_str.startswith("s:"):
            raise ValueError("Invalid sequence cursor format.")
        
        try:
            seq_part = decoded_str[2:]
            sequence = int(seq_part)
            if sequence < 0:
                raise ValueError("Sequence cannot be negative.")
            return sequence
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid sequence number in cursor: {e}") from e


def should_advance(current_sequence: int, target_sequence: int) -> bool:
    if not isinstance(current_sequence, int) or not isinstance(target_sequence, int):
        raise ValueError("Sequences must be integers.")
    return target_sequence > current_sequence
