from __future__ import annotations

import structlog

from camp_match.modules.booking.application.errors import (
    BookingNotFound,
    InvalidBookingStateTransition,
)
from camp_match.modules.booking.application.ports.inbound import ConfirmBookingRequest
from camp_match.modules.booking.application.ports.outbound import (
    AuthorizationService,
    BookingRepository,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock

logger = structlog.get_logger()


class ConfirmBookingUseCase:
    def __init__(
        self,
        booking_repo: BookingRepository,
        authorization_service: AuthorizationService,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.booking_repo = booking_repo
        self.authorization_service = authorization_service
        self.uow = uow
        self.clock = clock

    async def execute(self, request: ConfirmBookingRequest) -> None:
        # 1. Look up booking
        booking = await self.booking_repo.get_by_id(request.booking_id)
        if not booking:
            raise BookingNotFound("Booking not found.")

        # 2. Check hold expiry before anything else (ADR-097)
        if booking.is_hold_expired(self.clock):
            raise InvalidBookingStateTransition("Cannot confirm booking: hold has expired.")

        # 3. Authorize via BOOKING_CONFIRM
        await self.authorization_service.authorize(request.caller_id, Permission.BOOKING_CONFIRM)

        # 4. Concurrency-safe write (conditional UPDATE)
        now = self.clock.now()
        async with self.uow:
            updated = await self.booking_repo.confirm(booking.id, confirmed_at=now)
            if not updated:
                raise InvalidBookingStateTransition(
                    "Booking cannot be confirmed (already confirmed, cancelled, or expired)."
                )
            await self.uow.commit()

        logger.info(
            "booking_confirmed",
            booking_id=booking.id,
            caller_id=request.caller_id,
        )
