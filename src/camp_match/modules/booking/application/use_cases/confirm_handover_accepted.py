"""Confirm handover accepted use case."""
from __future__ import annotations

import structlog

from camp_match.modules.booking.application.errors import (
    BookingNotConfirmedForHandover,
    BookingNotFound,
    HandoverNotOffered,
)
from camp_match.modules.booking.application.ports.inbound import (
    ConfirmHandoverAcceptedRequest,
)
from camp_match.modules.booking.application.ports.outbound import BookingRepository
from camp_match.modules.booking.domain.events import HandoverAccepted
from camp_match.shared_kernel.application.errors import ForbiddenError
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

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
            raise ForbiddenError(
                "Only the booking student can confirm handover acceptance."
            )

        if booking.status.value != "CONFIRMED":
            raise BookingNotConfirmedForHandover(
                "Booking must be confirmed to accept handover."
            )

        if booking.handover_offered_at is None:
            raise HandoverNotOffered(
                "Handover must be offered by the scout before it can be accepted."
            )

        if booking.handover_accepted_at is not None:
            # Idempotent repeat: already accepted
            return

        now = self.clock.now()
        async with self.uow:
            matched = await self.booking_repo.confirm_handover_accepted(
                booking.id, accepted_at=now
            )
            if matched:
                event = HandoverAccepted(
                    event_id=EntityId.new(),
                    occurred_at=now,
                    booking_id=booking.id,
                    student_id=booking.student_id,
                    property_id=booking.property_id,
                    listing_id=booking.listing_id,
                )
                self.uow.add_event(event)
            await self.uow.commit()

        if matched:
            logger.info(
                "handover_accepted_confirmed",
                booking_id=booking.id,
                caller_id=request.caller_id,
            )
        else:
            current = await self.booking_repo.get_by_id(booking.id)
            if current and current.handover_accepted_at is not None:
                return
            if current and current.status.value != "CONFIRMED":
                raise BookingNotConfirmedForHandover(
                    "Booking must be confirmed to accept handover."
                )
            if current and current.handover_offered_at is None:
                raise HandoverNotOffered(
                    "Handover must be offered by the scout before it can be accepted."
                )
