from __future__ import annotations

import structlog

from camp_match.modules.booking.application.ports.inbound import ExpireHoldsResponse
from camp_match.modules.booking.application.ports.outbound import (
    BookingRepository,
    HousingProvider,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock

logger = structlog.get_logger()


class ExpireHoldsUseCase:
    def __init__(
        self,
        booking_repo: BookingRepository,
        housing_provider: HousingProvider,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.booking_repo = booking_repo
        self.housing_provider = housing_provider
        self.uow = uow
        self.clock = clock

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
                    logger.info("booking_hold_expired", booking_id=booking.id)

        return ExpireHoldsResponse(expired_count=expired_count)
