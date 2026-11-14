"""Saved listings domain entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, slots=True)
class SavedListing:
    user_id: EntityId
    listing_id: EntityId
    saved_at: datetime

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SavedListing):
            return NotImplemented
        return self.user_id == other.user_id and self.listing_id == other.listing_id

    def __hash__(self) -> int:
        return hash((self.user_id, self.listing_id))
