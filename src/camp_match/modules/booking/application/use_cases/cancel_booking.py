from __future__ import annotations

import structlog

from camp_match.modules.booking.application.errors import (
    BookingNotFound,
)
from camp_match.modules.booking.application.ports.inbound import CancelBookingRequest
from camp_match.modules.booking.application.ports.outbound import (
    AuthorizationService,
    BookingRepository,
    HousingProvider,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.errors import ForbiddenError, ValidationError
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock

logger = structlog.get_logger()


class CancelBookingUseCase:
    def __init__(
        self,
        booking_repo: BookingRepository,
        housing_provider: HousingProvider,
        authorization_service: AuthorizationService,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.booking_repo = booking_repo
        self.housing_provider = housing_provider
        self.authorization_service = authorization_service
        self.uow = uow
        self.clock = clock

    async def execute(self, request: CancelBookingRequest) -> None:
        if not request.cancellation_reason or not request.cancellation_reason.strip():
            raise ValidationError("Cancellation reason is required.")

        booking = await self.booking_repo.get_by_id(request.booking_id)
        if not booking:
            raise BookingNotFound("Booking not found.")

        # Dual-path authorization
        is_student_owner = request.caller_id == booking.student_id
        if not is_student_owner:
            provider_id = await self.housing_provider.get_property_owner(booking.property_id)
            try:
                await self.authorization_service.authorize(
                    request.caller_id, Permission.HOUSING_MANAGE, resource_owner_id=provider_id
                )
            except ForbiddenError:
                raise ForbiddenError("Caller is neither booking student nor property owner.")

        now = self.clock.now()
        async with self.uow:
            matched = await self.booking_repo.cancel(
                booking.id,
                cancelled_at=now,
                cancelled_by=request.caller_id,
                cancellation_reason=request.cancellation_reason.strip(),
            )
            await self.uow.commit()

        if matched:
            await self.housing_provider.release_slot(booking.unit_id)
            logger.info(
                "booking_cancelled",
                booking_id=booking.id,
                caller_id=request.caller_id,
            )
        else:
            # Already cancelled or expired -> idempotent no-op success, do NOT call release_slot (ADR-098)
            logger.info(
                "booking_cancellation_already_processed",
                booking_id=booking.id,
            )
