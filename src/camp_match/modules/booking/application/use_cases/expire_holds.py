"""Expire holds use case."""
from __future__ import annotations

import structlog

from camp_match.modules.booking.application.ports.inbound import (
    ExpireHoldsResponse,
)
from camp_match.modules.booking.application.ports.outbound import (
    BookingRepository,
    HousingProvider,
)
from camp_match.modules.booking.domain.events import BookingExpired
from camp_match.shared_kernel.application.event_bus import (
    EventBus,
    NoOpEventBus,
    publish_best_effort,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class ExpireHoldsUseCase:
    def __init__(
        self,
        booking_repo: BookingRepository,
        housing_provider: HousingProvider,
        uow: UnitOfWork,
        clock: Clock,
        event_bus: EventBus | None = None,
    ) -> None:
        self.booking_repo = booking_repo
        self.housing_provider = housing_provider
        self.uow = uow
        self.clock = clock
        self.event_bus = event_bus or NoOpEventBus()

    async def execute(self) -> ExpireHoldsResponse:
        now = self.clock.now()
        expired_bookings = await self.booking_repo.find_expired_holds(as_of=now)
        expired_count = 0

        for booking in expired_bookings:
            try:
                await self.housing_provider.release_slot(booking.unit_id)
            except Exception as e:
                logger.warning(
                    "failed_to_release_slot_for_expired_booking",
                    booking_id=booking.id,
                    unit_id=booking.unit_id,
                    error=str(e),
                )
                continue

            async with self.uow:
                updated = await self.booking_repo.expire(booking.id)
                if updated:
                    await self.uow.commit()
                    expired_count += 1
                    event = BookingExpired(
                        event_id=EntityId.new(),
                        occurred_at=now,
                        booking_id=booking.id,
                        student_id=booking.student_id,
                        property_id=booking.property_id,
                        listing_id=booking.listing_id,
                    )
                    await publish_best_effort(self.event_bus, event, logger)
                    logger.info("booking_hold_expired", booking_id=booking.id)

        return ExpireHoldsResponse(expired_count=expired_count)
