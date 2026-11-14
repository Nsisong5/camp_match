"""In-process saved state provider adapter for housing module."""

from __future__ import annotations

from camp_match.modules.housing.application.ports.outbound import SavedStateProvider
from camp_match.modules.saved_listings.application.ports.inbound import (
    GetSavedState,
    GetSavedStateQuery,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


class HousingSavedStateProviderAdapter(SavedStateProvider):
    def __init__(self, get_saved_state_uc: GetSavedState) -> None:
        self._get_saved_state_uc = get_saved_state_uc

    async def get_saved_state(
        self, viewer_id: EntityId | None, listing_ids: list[EntityId]
    ) -> set[EntityId]:
        if viewer_id is None or not listing_ids:
            return set()
        query = GetSavedStateQuery(user_id=viewer_id, listing_ids=listing_ids)
        return await self._get_saved_state_uc.execute(query)
