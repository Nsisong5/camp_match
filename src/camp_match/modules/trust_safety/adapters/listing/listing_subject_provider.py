"""In-process listing subject provider adapter for Trust & Safety."""
from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.housing.application.ports.outbound import ListingRepository, PropertyRepository
from camp_match.modules.trust_safety.application.ports.outbound import ListingSubject
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessListingSubjectProvider:
    def __init__(self, listing_repo: ListingRepository, property_repo: PropertyRepository) -> None:
        self._listing_repo = listing_repo
        self._property_repo = property_repo

    async def get_listing(self, listing_id: EntityId, viewer_id: EntityId) -> ListingSubject | None:
        try:
            listing = await self._listing_repo.get_by_id(listing_id)
            if not listing or listing.status.value == "ARCHIVED":
                return None
            prop = await self._property_repo.get_by_id(listing.property_id)
            if not prop:
                return None
            return ListingSubject(
                listing_id=listing.id,
                owner_id=prop.provider_id,
                status=listing.status.value,
            )
        except Exception:
            return None
