"""Saved listings outbound ports and DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from camp_match.modules.saved_listings.domain.entities import SavedListing
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True)
class ListingSavingInfo:
    owner_id: EntityId
    is_public: bool


@dataclass(frozen=True)
class ListingCard:
    state: str  # "AVAILABLE" | "FULLY_BOOKED" | "UNAVAILABLE"
    data: dict[str, Any] | None = None


class SavedListingRepository(Protocol):
    async def add(self, saved: SavedListing, max_per_user: int) -> bool: ...
    async def remove(self, user_id: EntityId, listing_id: EntityId) -> bool: ...
    async def list_page(
        self, user_id: EntityId, page: PageRequest
    ) -> Page[SavedListing]: ...
    async def saved_among(
        self, user_id: EntityId, listing_ids: list[EntityId]
    ) -> set[EntityId]: ...
    async def get(
        self, user_id: EntityId, listing_id: EntityId
    ) -> SavedListing | None: ...


class ListingCatalogProvider(Protocol):
    async def get_for_saving(
        self, listing_id: EntityId
    ) -> ListingSavingInfo | None: ...
    async def get_cards(
        self, listing_ids: list[EntityId]
    ) -> dict[EntityId, ListingCard]: ...
