from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from camp_match.modules.booking.adapters.persistence.repository import SqlAlchemyBookingRepository
from camp_match.modules.booking.application.use_cases.invalidate_bookings_for_listing import (
    InvalidateBookingsForListingUseCase,
)
from camp_match.modules.booking.domain.entities import Booking
from camp_match.modules.booking.domain.value_objects import (
    BillingPeriod,
    BookingStatus,
    ClosureCode,
    Currency,
    PriceSnapshot,
)
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from tests.support.fixed_clock import FixedClock
from camp_match.shared_kernel.domain.identifiers import EntityId


class FakeHousingProvider:
    def __init__(self) -> None:
        self.released_slots = 0

    async def release_slot(self, unit_id: EntityId) -> None:
        self.released_slots += 1


@pytest.mark.anyio
async def test_closure_messages_and_invalidation(db_session, session_factory) -> None:
    # 1. Test closure codes and messages
    for code in ClosureCode:
        assert code.message

    # 2. Test InvalidateBookingsForListingUseCase
    housing_provider = FakeHousingProvider()
    clock = FixedClock(datetime.now(timezone.utc))
    settings = type("Settings", (), {"booking_invalidation_batch_size": 10})()

    listing_id = EntityId.new()
    unit_id = EntityId.new()
    prop_id = EntityId.new()
    student_id = EntityId.new()

    booking = Booking(
        id=EntityId.new(),
        student_id=student_id,
        listing_id=listing_id,
        unit_id=unit_id,
        property_id=prop_id,
        status=BookingStatus.CONFIRMED,
        price=PriceSnapshot(amount_kobo=5000, currency=Currency.NGN, period=BillingPeriod.MONTH),
        verification_confirmed_at_booking=True,
        idempotency_key="key-1",
        expires_at=clock.now() + timedelta(hours=1),
        created_at=clock.now(),
        confirmed_at=clock.now(),
    )

    async with session_factory() as session:
        repo = SqlAlchemyBookingRepository(session)
        uow = SqlAlchemyUnitOfWork(session)
        async with uow:
            await repo.add(booking)
            await uow.commit()

    invalidate_uc = InvalidateBookingsForListingUseCase(session_factory, housing_provider, clock, settings)
    count = await invalidate_uc(listing_id, "LISTING_SUSPENDED", EntityId.new())

    assert count == 1
    assert housing_provider.released_slots == 1

    async with session_factory() as session:
        repo = SqlAlchemyBookingRepository(session)
        updated = await repo.get_by_id(booking.id)
        assert updated.status == BookingStatus.CANCELLED
        assert updated.closure_code == "LISTING_SUSPENDED"
        assert updated.closure.code == "LISTING_SUSPENDED"
        assert "suspended" in updated.closure.message

    # Replay invalidation (idempotency / already closed skip)
    count_replay = await invalidate_uc(listing_id, "LISTING_SUSPENDED", EntityId.new())
    assert count_replay == 0
    assert housing_provider.released_slots == 1  # slot not released twice
