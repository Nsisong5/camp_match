"""Get listing for saving use case (Housing module)."""

from __future__ import annotations

from camp_match.modules.housing.application.ports.inbound import ListingSavingInfoResponse
from camp_match.modules.housing.application.ports.outbound import (
    ListingRepository,
    PropertyRepository,
)
from camp_match.modules.housing.domain.value_objects import ListingStatus
from camp_match.shared_kernel.domain.identifiers import EntityId


class GetListingForSavingUseCase:
    def __init__(
        self,
        listing_repo: ListingRepository,
        property_repo: PropertyRepository,
    ) -> None:
        self._listing_repo = listing_repo
        self._property_repo = property_repo

    async def __call__(self, listing_id: EntityId) -> ListingSavingInfoResponse | None:
        listing = await self._listing_repo.get_by_id(listing_id)
        if not listing:
            return None
        prop = await self._property_repo.get_by_id(listing.property_id)
        if not prop:
            return None
        is_public = listing.status == ListingStatus.PUBLISHED
        return ListingSavingInfoResponse(owner_id=prop.provider_id, is_public=is_public)
