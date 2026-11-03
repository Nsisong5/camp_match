from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.booking.application.errors import BookingNotFound
from camp_match.modules.booking.application.ports.inbound import GetBookingRequest
from camp_match.modules.booking.application.use_cases.get_booking import GetBookingUseCase
from camp_match.modules.messaging.application.ports.outbound import BookingContext
from camp_match.shared_kernel.application.errors import ForbiddenError
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from camp_match.modules.booking.adapters.persistence.repository import (
        SqlAlchemyBookingRepository,
    )
    from camp_match.modules.booking.application.ports.outbound import (
        AuthorizationService,
        HousingProvider,
    )


class InProcessBookingProvider:
    def __init__(
        self,
        booking_repo: SqlAlchemyBookingRepository,
        housing_provider: HousingProvider,
        authorization_service: AuthorizationService,
    ) -> None:
        self._get_booking_uc = GetBookingUseCase(
            booking_repo=booking_repo,
            housing_provider=housing_provider,
            authorization_service=authorization_service,
        )

    async def get_booking_context(self, booking_id: EntityId, requester_id: EntityId) -> BookingContext | None:
        try:
            booking = await self._get_booking_uc.execute(
                GetBookingRequest(booking_id=booking_id, caller_id=requester_id)
            )
        except (BookingNotFound, ForbiddenError):
            return None

        return BookingContext(
            student_id=booking.student_id,
            property_id=booking.property_id,
            listing_id=booking.listing_id,
            status=booking.status.value if hasattr(booking.status, "value") else str(booking.status),
        )
