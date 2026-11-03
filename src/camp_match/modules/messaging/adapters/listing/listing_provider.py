from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.messaging.application.ports.outbound import ListingContext
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from camp_match.modules.housing.adapters.persistence.repository import (
        SqlAlchemyListingRepository,
        SqlAlchemyPropertyRepository,
    )


class InProcessListingProvider:
    def __init__(
        self,
        listing_repo: SqlAlchemyListingRepository,
        property_repo: SqlAlchemyPropertyRepository,
    ) -> None:
        self._listing_repo = listing_repo
        self._property_repo = property_repo

    async def get_listing_context(self, listing_id: EntityId) -> ListingContext | None:
        listing = await self._listing_repo.get_by_id(listing_id)
        if not listing:
            return None
        property_obj = await self._property_repo.get_by_id(listing.property_id)
        if not property_obj:
            return None
        return ListingContext(
            provider_id=property_obj.provider_id,
            status=listing.status.value if hasattr(listing.status, "value") else str(listing.status),
        )

    async def get_property_owner(self, property_id: EntityId) -> EntityId | None:
        property_obj = await self._property_repo.get_by_id(property_id)
        if not property_obj:
            return None
        return property_obj.provider_id
