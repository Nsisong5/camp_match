"""Unsave listing use case."""

from __future__ import annotations

from camp_match.modules.saved_listings.application.ports.inbound import UnsaveListingCommand
from camp_match.modules.saved_listings.application.ports.outbound import SavedListingRepository


class UnsaveListingUseCase:
    def __init__(self, saved_repo: SavedListingRepository) -> None:
        self._saved_repo = saved_repo

    async def execute(self, cmd: UnsaveListingCommand) -> None:
        await self._saved_repo.remove(cmd.user_id, cmd.listing_id)
