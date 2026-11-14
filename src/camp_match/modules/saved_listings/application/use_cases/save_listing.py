"""Save listing use case."""

from __future__ import annotations

from camp_match.modules.saved_listings.application.errors import (
    CannotSaveOwnListing,
    ListingNotSavable,
)
from camp_match.modules.saved_listings.application.ports.inbound import (
    SaveListingCommand,
    SaveListingResult,
)
from camp_match.modules.saved_listings.application.ports.outbound import (
    ListingCatalogProvider,
    SavedListingRepository,
)
from camp_match.modules.saved_listings.domain.entities import SavedListing
from camp_match.shared_kernel.domain.clock import Clock


class SaveListingUseCase:
    def __init__(
        self,
        saved_repo: SavedListingRepository,
        catalog_provider: ListingCatalogProvider,
        clock: Clock,
        max_per_user: int = 200,
    ) -> None:
        self._saved_repo = saved_repo
        self._catalog_provider = catalog_provider
        self._clock = clock
        self._max_per_user = max_per_user

    async def execute(self, cmd: SaveListingCommand) -> SaveListingResult:
        info = await self._catalog_provider.get_for_saving(cmd.listing_id)
        if info is None or not info.is_public:
            raise ListingNotSavable("Listing not found or not published.")
        if info.owner_id == cmd.user_id:
            raise CannotSaveOwnListing("Cannot save your own listing.")

        existing = await self._saved_repo.get(cmd.user_id, cmd.listing_id)
        if existing is not None:
            return SaveListingResult(
                listing_id=cmd.listing_id,
                saved_at=existing.saved_at,
                already_saved=True,
            )

        now = self._clock.now()
        saved = SavedListing(
            user_id=cmd.user_id, listing_id=cmd.listing_id, saved_at=now
        )
        newly_added = await self._saved_repo.add(saved, self._max_per_user)

        if not newly_added:
            existing_after = await self._saved_repo.get(cmd.user_id, cmd.listing_id)
            saved_at = existing_after.saved_at if existing_after else now
            return SaveListingResult(
                listing_id=cmd.listing_id,
                saved_at=saved_at,
                already_saved=True,
            )

        return SaveListingResult(
            listing_id=cmd.listing_id,
            saved_at=now,
            already_saved=False,
        )
