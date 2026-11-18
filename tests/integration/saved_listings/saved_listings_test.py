from __future__ import annotations

from datetime import UTC, datetime
import pytest
from sqlalchemy import select

from camp_match.config.settings import get_settings
from camp_match.modules.saved_listings.adapters.persistence.models import SavedListingModel
from camp_match.modules.saved_listings.adapters.persistence.repository import (
    SqlAlchemySavedListingRepository,
)
from camp_match.modules.saved_listings.domain.entities import SavedListing
from camp_match.shared_kernel.domain.identifiers import EntityId
from tests.support.fixed_clock import FixedClock


@pytest.mark.asyncio
async def test_saved_listing_persistence_and_commit(clear_db, session_factory) -> None:
    clock = FixedClock(datetime(2026, 11, 15, 4, 20, 18, tzinfo=UTC))
    user_id = EntityId.new()
    listing_id = EntityId.new()

    # 1. Add saved listing using repository in a session
    async with session_factory() as session:
        repo = SqlAlchemySavedListingRepository(session)
        saved = SavedListing(user_id=user_id, listing_id=listing_id, saved_at=clock.now())
        added = await repo.add(saved, max_per_user=200)
        assert added is True

    # 2. Verify in a fresh session that the record was committed to the DB
    async with session_factory() as session:
        repo = SqlAlchemySavedListingRepository(session)
        fetched = await repo.get(user_id, listing_id)
        assert fetched is not None
        assert fetched.user_id == user_id
        assert fetched.listing_id == listing_id

        # Trying to add again should return False (already saved)
        added_again = await repo.add(saved, max_per_user=200)
        assert added_again is False

        # Remove should delete and commit
        removed = await repo.remove(user_id, listing_id)
        assert removed is True

    # 3. Verify in another fresh session that removal was committed
    async with session_factory() as session:
        repo = SqlAlchemySavedListingRepository(session)
        fetched_after_remove = await repo.get(user_id, listing_id)
        assert fetched_after_remove is None
