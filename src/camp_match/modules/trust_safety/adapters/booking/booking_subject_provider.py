"""In-process booking subject provider adapter for Trust & Safety."""
from __future__ import annotations

from camp_match.modules.booking.application.ports.inbound import GetBookingRequest
from camp_match.modules.booking.application.use_cases.get_booking import GetBookingUseCase
from camp_match.modules.housing.application.ports.outbound import PropertyRepository
from camp_match.modules.trust_safety.application.ports.outbound import BookingSubject
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessBookingSubjectProvider:
    def __init__(self, get_booking_uc: GetBookingUseCase, property_repo: PropertyRepository) -> None:
        self._get_booking_uc = get_booking_uc
        self._property_repo = property_repo

    async def get_booking(self, booking_id: EntityId, viewer_id: EntityId) -> BookingSubject | None:
        try:
            booking = await self._get_booking_uc.execute(GetBookingRequest(booking_id=booking_id, caller_id=viewer_id))
            prop = await self._property_repo.get_by_id(booking.property_id)
            if not prop:
                return None
            return BookingSubject(
                booking_id=booking.id,
                student_id=booking.student_id,
                provider_id=prop.provider_id,
            )
        except Exception:
            return None
