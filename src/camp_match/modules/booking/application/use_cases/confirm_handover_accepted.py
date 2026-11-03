from __future__ import annotations

import structlog

from camp_match.modules.booking.application.errors import BookingNotFound
from camp_match.modules.booking.application.ports.inbound import ConfirmHandoverAcceptedRequest
from camp_match.modules.booking.application.ports.outbound import BookingRepository
from camp_match.shared_kernel.application.errors import ForbiddenError, ValidationError
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock

logger = structlog.get_logger()


class ConfirmHandoverAcceptedUseCase:
    def __init__(
        self,
        booking_repo: BookingRepository,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.booking_repo = booking_repo
        self.uow = uow
        self.clock = clock

    async def execute(self, request: ConfirmHandoverAcceptedRequest) -> None:
        booking = await self.booking_repo.get_by_id(request.booking_id)
        if not booking:
            raise BookingNotFound("Booking not found.")

        if request.caller_id != booking.student_id:
            raise ForbiddenError("Only the booking student can confirm handover acceptance.")

        if booking.status.value != "CONFIRMED":
            raise ValidationError("Booking must be confirmed to accept handover.")

        if booking.handover_offered_at is None:
            raise ValidationError("Handover must be offered by the scout before it can be accepted.")

        now = self.clock.now()
        async with self.uow:
            matched = await self.booking_repo.confirm_handover_accepted(
                booking.id, accepted_at=now
            )
            await self.uow.commit()

        if matched:
            logger.info(
                "handover_accepted_confirmed",
                booking_id=booking.id,
                caller_id=request.caller_id,
            )
        else:
            raise ValidationError("Handover has already been accepted or state changed.")
