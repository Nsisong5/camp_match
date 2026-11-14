from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from camp_match.modules.booking.adapters.persistence.repository import SqlAlchemyBookingRepository
from camp_match.modules.booking.application.use_cases.publish_booking_reminders import PublishBookingRemindersUseCase
from camp_match.modules.booking.application.use_cases.reconcile_suspended_listing_bookings import ReconcileSuspendedListingBookingsUseCase
from camp_match.modules.booking.domain.entities import Booking
from camp_match.modules.booking.domain.value_objects import (
    BillingPeriod,
    BookingStatus,
    Currency,
    PriceSnapshot,
)
from camp_match.modules.housing.adapters.events.identity_subscriber import register_identity_subscribers
from camp_match.modules.booking.adapters.events.housing_subscriber import register_housing_subscribers
from camp_match.platform.in_memory_event_bus import InMemoryEventBus
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from tests.support.fixed_clock import FixedClock
from camp_match.shared_kernel.domain.identifiers import EntityId


class MockHousingProvider:
    def __init__(self, suspended_ids: list[EntityId], reasons: dict[EntityId, str]) -> None:
        self.suspended_ids = suspended_ids
        self.reasons = reasons
        self.released_slots = 0

    async def list_suspended_listing_ids(self, limit: int, after_id: EntityId | None) -> list[EntityId]:
        return self.suspended_ids

    async def get_listing_suspension_reason(self, listing_id: EntityId) -> str | None:
        return self.reasons.get(listing_id, "SAFETY_ENFORCEMENT")

    async def release_slot(self, unit_id: EntityId) -> None:
        self.released_slots += 1


@pytest.mark.anyio
async def test_chunk_12_reconcile_and_reminders(db_session, session_factory) -> None:
    clock = FixedClock(datetime.now(timezone.utc))
    settings = type(
        "Settings",
        (),
        {
            "booking_invalidation_batch_size": 10,
            "booking_handover_reminder_after_seconds": 3600,
            "booking_acceptance_reminder_after_seconds": 3600,
        },
    )()

    listing_id = EntityId.new()
    unit_id = EntityId.new()
    prop_id = EntityId.new()
    student_id = EntityId.new()

    # Create confirmed booking older than reminder threshold
    confirmed_at = clock.now() - timedelta(hours=2)
    booking = Booking(
        id=EntityId.new(),
        student_id=student_id,
        listing_id=listing_id,
        unit_id=unit_id,
        property_id=prop_id,
        status=BookingStatus.CONFIRMED,
        price=PriceSnapshot(amount_kobo=5000, currency=Currency.NGN, period=BillingPeriod.MONTH),
        verification_confirmed_at_booking=True,
        idempotency_key="key-remind-1",
        expires_at=clock.now() + timedelta(hours=1),
        created_at=confirmed_at,
        confirmed_at=confirmed_at,
    )

    async with session_factory() as session:
        repo = SqlAlchemyBookingRepository(session)
        uow = SqlAlchemyUnitOfWork(session)
        async with uow:
            await repo.add(booking)
            await uow.commit()

    # 1. Test PublishBookingRemindersUseCase
    reminders_uc = PublishBookingRemindersUseCase(session_factory, clock, settings)
    published_count = await reminders_uc(limit=10)
    assert published_count == 1

    # Replay reminders (idempotency)
    published_count_replay = await reminders_uc(limit=10)
    assert published_count_replay == 0

    # 2. Test ReconcileSuspendedListingBookingsUseCase
    housing_provider = MockHousingProvider(
        suspended_ids=[listing_id],
        reasons={listing_id: "SAFETY_ENFORCEMENT"},
    )
    reconcile_uc = ReconcileSuspendedListingBookingsUseCase(
        session_factory, housing_provider, clock, settings
    )
    invalidated_count = await reconcile_uc(limit=10)
    assert invalidated_count == 1
    assert housing_provider.released_slots == 1
