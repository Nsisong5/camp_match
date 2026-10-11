from __future__ import annotations

from camp_match.modules.booking.application.ports.inbound import ListMyBookingsRequest
from camp_match.modules.booking.application.ports.outbound import BookingRepository
from camp_match.modules.booking.domain.entities import Booking
from camp_match.shared_kernel.application.pagination import Page


class ListMyBookingsUseCase:
    def __init__(self, booking_repo: BookingRepository) -> None:
        self.booking_repo = booking_repo

    async def execute(self, request: ListMyBookingsRequest) -> Page[Booking]:
        return await self.booking_repo.find_by_student(request.caller_id, request.page)
