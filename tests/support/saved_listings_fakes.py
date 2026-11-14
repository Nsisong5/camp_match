"""Shared fakes for saved listings module tests."""

from __future__ import annotations

from camp_match.modules.saved_listings.application.errors import SavedLimitReached
from camp_match.modules.saved_listings.application.ports.outbound import (
    ListingCard,
    ListingSavingInfo,
)
from camp_match.modules.saved_listings.domain.entities import SavedListing
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class InMemorySavedListingRepository:
    def __init__(self) -> None:
        self._storage: dict[tuple[EntityId, EntityId], SavedListing] = {}

    async def add(self, saved: SavedListing, max_per_user: int) -> bool:
        key = (saved.user_id, saved.listing_id)
        if key in self._storage:
            return False

        user_saves_count = sum(
            1 for (uid, _), _ in self._storage.items() if uid == saved.user_id
        )
        if user_saves_count >= max_per_user:
            raise SavedLimitReached("Saved limit reached.")

        self._storage[key] = saved
        return True

    async def remove(self, user_id: EntityId, listing_id: EntityId) -> bool:
        key = (user_id, listing_id)
        if key in self._storage:
            del self._storage[key]
            return True
        return False

    async def list_page(
        self, user_id: EntityId, page: PageRequest
    ) -> Page[SavedListing]:
        user_items = [s for (uid, _), s in self._storage.items() if uid == user_id]
        user_items.sort(key=lambda x: (-x.saved_at.timestamp(), str(x.listing_id)))

        total = len(user_items)
        start = (page.page - 1) * page.page_size
        end = start + page.page_size
        items = user_items[start:end]

        return Page(items=items, total=total, page=page.page, page_size=page.page_size)

    async def saved_among(
        self, user_id: EntityId, listing_ids: list[EntityId]
    ) -> set[EntityId]:
        return {lid for lid in listing_ids if (user_id, lid) in self._storage}

    async def get(self, user_id: EntityId, listing_id: EntityId) -> SavedListing | None:
        return self._storage.get((user_id, listing_id))


class FakeListingCatalogProvider:
    def __init__(self) -> None:
        self.listings: dict[EntityId, ListingSavingInfo] = {}
        self.cards: dict[EntityId, ListingCard] = {}
        self.get_cards_call_count: int = 0

    async def get_for_saving(
        self, listing_id: EntityId
    ) -> ListingSavingInfo | None:
        return self.listings.get(listing_id)

    async def get_cards(
        self, listing_ids: list[EntityId]
    ) -> dict[EntityId, ListingCard]:
        self.get_cards_call_count += 1
        return {
            lid: self.cards.get(lid, ListingCard(state="UNAVAILABLE"))
            for lid in listing_ids
        }
