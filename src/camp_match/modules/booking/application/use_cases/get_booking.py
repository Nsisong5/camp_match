from __future__ import annotations

from camp_match.modules.booking.application.errors import BookingNotFound
from camp_match.modules.booking.application.ports.inbound import GetBookingRequest
from camp_match.modules.booking.application.ports.outbound import (
    AuthorizationService,
    BookingRepository,
    HousingProvider,
)
from camp_match.modules.booking.domain.entities import Booking
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.errors import ForbiddenError


class GetBookingUseCase:
    def __init__(
        self,
        booking_repo: BookingRepository,
        housing_provider: HousingProvider,
        authorization_service: AuthorizationService,
    ) -> None:
        self.booking_repo = booking_repo
        self.housing_provider = housing_provider
        self.authorization_service = authorization_service

    async def execute(self, request: GetBookingRequest) -> Booking:
        booking = await self.booking_repo.get_by_id(request.booking_id)
        if not booking:
            raise BookingNotFound("Booking not found.")

        is_student_owner = request.caller_id == booking.student_id
        if not is_student_owner:
            provider_id = await self.housing_provider.get_property_owner(booking.property_id)
            try:
                await self.authorization_service.authorize(
                    request.caller_id, Permission.HOUSING_MANAGE, resource_owner_id=provider_id
                )
            except ForbiddenError:
                raise ForbiddenError("Caller is neither booking student nor property owner.")

        return booking
