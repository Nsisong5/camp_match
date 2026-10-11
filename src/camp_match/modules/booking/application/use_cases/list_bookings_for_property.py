from __future__ import annotations

from camp_match.modules.booking.application.ports.inbound import ListBookingsForPropertyRequest
from camp_match.modules.booking.application.ports.outbound import (
    AuthorizationService,
    BookingRepository,
    HousingProvider,
)
from camp_match.modules.booking.domain.entities import Booking
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.pagination import Page


class ListBookingsForPropertyUseCase:
    def __init__(
        self,
        booking_repo: BookingRepository,
        housing_provider: HousingProvider,
        authorization_service: AuthorizationService,
    ) -> None:
        self.booking_repo = booking_repo
        self.housing_provider = housing_provider
        self.authorization_service = authorization_service

    async def execute(self, request: ListBookingsForPropertyRequest) -> Page[Booking]:
        provider_id = await self.housing_provider.get_property_owner(request.property_id)
        await self.authorization_service.authorize(
            request.caller_id, Permission.HOUSING_MANAGE, resource_owner_id=provider_id
        )
        return await self.booking_repo.find_by_property(request.property_id, request.page)
