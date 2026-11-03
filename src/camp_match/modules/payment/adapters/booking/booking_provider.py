from __future__ import annotations

from camp_match.modules.booking.adapters.persistence.repository import SqlAlchemyBookingRepository
from camp_match.modules.payment.application.ports.outbound import BookingProvider, BookingSummary
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessBookingProvider(BookingProvider):
    def __init__(self, booking_repo: SqlAlchemyBookingRepository) -> None:
        self._booking_repo = booking_repo

    async def get_booking(self, booking_id: EntityId) -> BookingSummary | None:
        booking = await self._booking_repo.get_by_id(booking_id)
        if not booking:
            return None
        return BookingSummary(
            id=booking.id,
            status=booking.status.value,
            student_id=booking.student_id,
            property_id=booking.property_id,
            amount_kobo=booking.price.amount_kobo,
            currency=booking.price.currency.value,
            period=booking.price.period.value,
            expires_at=booking.expires_at,
            handover_offered_at=booking.handover_offered_at,
            handover_accepted_at=booking.handover_accepted_at,
        )
