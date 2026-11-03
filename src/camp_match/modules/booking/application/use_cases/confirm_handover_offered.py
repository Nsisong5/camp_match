from __future__ import annotations

import structlog

from camp_match.modules.booking.application.errors import BookingNotFound
from camp_match.modules.booking.application.ports.inbound import ConfirmHandoverOfferedRequest
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


class ConfirmHandoverOfferedUseCase:
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

    async def execute(self, request: ConfirmHandoverOfferedRequest) -> None:
        booking = await self.booking_repo.get_by_id(request.booking_id)
        if not booking:
            raise BookingNotFound("Booking not found.")

        provider_id = await self.housing_provider.get_property_owner(booking.property_id)
        try:
            await self.authorization_service.authorize(
                request.caller_id, Permission.HOUSING_MANAGE, resource_owner_id=provider_id
            )
        except ForbiddenError:
            raise ForbiddenError("Only the property owner can confirm handover offered.")

        if booking.status.value != "CONFIRMED":
            raise ValidationError("Booking must be confirmed to offer handover.")

        now = self.clock.now()
        async with self.uow:
            matched = await self.booking_repo.confirm_handover_offered(
                booking.id, offered_at=now, offered_by=request.caller_id
            )
            await self.uow.commit()

        if matched:
            logger.info(
                "handover_offered_confirmed",
                booking_id=booking.id,
                caller_id=request.caller_id,
            )
        else:
            raise ValidationError("Handover has already been offered or booking state changed.")
