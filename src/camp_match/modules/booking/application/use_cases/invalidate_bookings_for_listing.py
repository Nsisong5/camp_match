"""Invalidate bookings for listing use case."""
from __future__ import annotations

import structlog
from typing import Any

from camp_match.modules.booking.adapters.persistence.repository import (
    SqlAlchemyBookingRepository,
)
from camp_match.modules.booking.domain.events import BookingInvalidated
from camp_match.modules.booking.domain.value_objects import BookingStatus
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger(__name__)


class InvalidateBookingsForListingUseCase:
    def __init__(
        self,
        session_factory: Any,
        housing_provider: Any,
        clock: Clock,
        settings: Any,
    ) -> None:
        self.session_factory = session_factory
        self.housing_provider = housing_provider
        self.clock = clock
        self.settings = settings

    async def __call__(
        self,
        listing_id: EntityId,
        reason_code: str,
        source_event_id: EntityId,
    ) -> int:
        batch_size = getattr(self.settings, "booking_invalidation_batch_size", 50)
        invalidated_count = 0

        while True:
            async with self.session_factory() as session:
                booking_repo = SqlAlchemyBookingRepository(session)
                bookings = await booking_repo.list_active_by_listing(
                    listing_id, batch_size
                )
            if not bookings:
                break

            for booking in bookings:
                try:
                    async with self.session_factory() as session:
                        booking_repo = SqlAlchemyBookingRepository(session)
                        uow = SqlAlchemyUnitOfWork(session)

                        now = self.clock.now()
                        was_confirmed = booking.status == BookingStatus.CONFIRMED
                        matched = await booking_repo.invalidate(
                            booking.id,
                            cancelled_at=now,
                            closure_code=reason_code,
                        )
                        if matched:
                            await self.housing_provider.release_slot(booking.unit_id)
                            uow.add_event(
                                BookingInvalidated(
                                    booking_id=booking.id,
                                    student_id=booking.student_id,
                                    property_id=booking.property_id,
                                    listing_id=booking.listing_id,
                                    reason_code=reason_code,
                                    was_confirmed=was_confirmed,
                                )
                            )
                            await uow.commit()
                            invalidated_count += 1
                            logger.info(
                                "booking_invalidated",
                                booking_id=booking.id,
                                listing_id=listing_id,
                                reason_code=reason_code,
                            )
                except Exception as e:
                    logger.warning(
                        "failed_to_invalidate_booking",
                        booking_id=booking.id,
                        error=str(e),
                    )

            if len(bookings) < batch_size:
                break

        return invalidated_count
