"""Get saved state use case."""

from __future__ import annotations

from camp_match.modules.saved_listings.application.ports.inbound import GetSavedStateQuery
from camp_match.modules.saved_listings.application.ports.outbound import SavedListingRepository
from camp_match.shared_kernel.domain.identifiers import EntityId


class GetSavedStateUseCase:
    def __init__(self, saved_repo: SavedListingRepository) -> None:
        self._saved_repo = saved_repo

    async def execute(self, query: GetSavedStateQuery) -> set[EntityId]:
        if not query.listing_ids:
            return set()
        return await self._saved_repo.saved_among(query.user_id, query.listing_ids)
