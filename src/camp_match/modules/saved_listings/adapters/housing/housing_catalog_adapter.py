"""In-process housing catalog adapter for saved listings."""

from __future__ import annotations

from camp_match.modules.housing.application.ports.inbound import (
    GetListingCards,
    GetListingForSaving,
)
from camp_match.modules.saved_listings.application.ports.outbound import (
    ListingCard,
    ListingCatalogProvider,
    ListingSavingInfo,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


class HousingCatalogAdapter(ListingCatalogProvider):
    def __init__(
        self,
        get_listing_for_saving_uc: GetListingForSaving,
        get_listing_cards_uc: GetListingCards,
    ) -> None:
        self._get_for_saving_uc = get_listing_for_saving_uc
        self._get_cards_uc = get_listing_cards_uc

    async def get_for_saving(self, listing_id: EntityId) -> ListingSavingInfo | None:
        res = await self._get_for_saving_uc(listing_id)
        if res is None:
            return None
        return ListingSavingInfo(owner_id=res.owner_id, is_public=res.is_public)

    async def get_cards(
        self, listing_ids: list[EntityId]
    ) -> dict[EntityId, ListingCard]:
        cards_dict = await self._get_cards_uc(listing_ids)
        result: dict[EntityId, ListingCard] = {}
        for lid, hcard in cards_dict.items():
            result[lid] = ListingCard(state=hcard.state, data=hcard.data)
        return result
