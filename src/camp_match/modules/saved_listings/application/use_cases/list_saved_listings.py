"""List saved listings use case."""

from __future__ import annotations

from camp_match.modules.saved_listings.application.ports.inbound import (
    ListSavedListingsQuery,
    SavedListingItem,
)
from camp_match.modules.saved_listings.application.ports.outbound import (
    ListingCatalogProvider,
    SavedListingRepository,
)
from camp_match.shared_kernel.application.pagination import Page


class ListSavedListingsUseCase:
    def __init__(
        self,
        saved_repo: SavedListingRepository,
        catalog_provider: ListingCatalogProvider,
    ) -> None:
        self._saved_repo = saved_repo
        self._catalog_provider = catalog_provider

    async def execute(self, query: ListSavedListingsQuery) -> Page[SavedListingItem]:
        page = await self._saved_repo.list_page(query.user_id, query.page_request)
        if not page.items:
            return Page(items=[], total=page.total, page=page.page, page_size=page.page_size)

        listing_ids = [item.listing_id for item in page.items]
        cards = await self._catalog_provider.get_cards(listing_ids)

        items: list[SavedListingItem] = []
        for saved in page.items:
            card = cards.get(saved.listing_id)
            if card is None or card.state == "UNAVAILABLE":
                availability = "UNAVAILABLE"
                listing = None
            else:
                availability = card.state  # "AVAILABLE" or "FULLY_BOOKED"
                listing = card.data

            items.append(
                SavedListingItem(
                    listing_id=saved.listing_id,
                    saved_at=saved.saved_at,
                    availability=availability,
                    listing=listing,
                )
            )

        return Page(items=items, total=page.total, page=page.page, page_size=page.page_size)
