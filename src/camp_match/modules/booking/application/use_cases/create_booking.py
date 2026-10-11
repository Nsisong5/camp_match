from __future__ import annotations

from datetime import timedelta
import structlog

from camp_match.config.settings import Settings
from camp_match.modules.booking.application.errors import (
    InventoryUnavailable,
    ListingNotBookable,
    SelfBookingNotAllowed,
    VerificationRequirementNotSatisfied,
)
from camp_match.modules.booking.application.ports.inbound import (
    CreateBookingRequest,
)
from camp_match.modules.booking.application.ports.outbound import (
    BookingRepository,
    HousingProvider,
    VerificationProvider,
)
from camp_match.modules.booking.domain.entities import Booking
from camp_match.modules.booking.domain.value_objects import (
    BillingPeriod,
    BookingStatus,
    Currency,
    PriceSnapshot,
)
from camp_match.modules.verification.domain.value_objects import VerificationTargetType
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class CreateBookingUseCase:
    def __init__(
        self,
        booking_repo: BookingRepository,
        housing_provider: HousingProvider,
        verification_provider: VerificationProvider,
        uow: UnitOfWork,
        clock: Clock,
        settings: Settings,
    ) -> None:
        self.booking_repo = booking_repo
        self.housing_provider = housing_provider
        self.verification_provider = verification_provider
        self.uow = uow
        self.clock = clock
        self.settings = settings

    async def execute(self, request: CreateBookingRequest) -> Booking:
        # 1. Idempotency check first
        existing = await self.booking_repo.get_by_idempotency_key(
            request.student_id, request.idempotency_key
        )
        if existing:
            return existing

        # 2. Resolve listing
        listing = await self.housing_provider.get_listing(request.listing_id)
        if not listing:
            raise ListingNotBookable("Listing not found or not bookable.")

        # 3. Self-booking check
        provider_id = await self.housing_provider.get_property_owner(listing.property_id)
        if provider_id == request.student_id:
            raise SelfBookingNotAllowed("Cannot book your own property.")

        # 4. Listing-state check
        if listing.status != "PUBLISHED":
            raise ListingNotBookable("Listing is not published.")

        # 5. Verification check
        ver_status = await self.verification_provider.get_verification_status(
            VerificationTargetType.PROPERTY, listing.property_id
        )
        if not ver_status.is_verified:
            raise VerificationRequirementNotSatisfied("Property must be verified before booking.")

        # 6. Reserve inventory
        reserved = await self.housing_provider.reserve_slot(listing.unit_id)
        if not reserved:
            raise InventoryUnavailable("Inventory unavailable for this unit.")

        # 7. Construct booking entity & persist with compensating release on failure
        now = self.clock.now()
        expires_at = now + timedelta(minutes=self.settings.booking_hold_duration_minutes)

        booking = Booking(
            id=EntityId.new(),
            student_id=request.student_id,
            listing_id=listing.id,
            unit_id=listing.unit_id,
            property_id=listing.property_id,
            status=BookingStatus.AWAITING_PAYMENT,
            price=PriceSnapshot(
                amount_kobo=listing.price_amount_kobo,
                currency=Currency(listing.price_currency),
                period=BillingPeriod(listing.price_period),
            ),
            verification_confirmed_at_booking=True,
            idempotency_key=request.idempotency_key,
            expires_at=expires_at,
            created_at=now,
        )

        try:
            async with self.uow:
                saved = await self.booking_repo.add(booking)
                await self.uow.commit()
        except Exception as e:
            logger.error(
                "booking_persistence_failed_compensating_reservation",
                listing_id=listing.id,
                unit_id=listing.unit_id,
                error=str(e),
            )
            await self.housing_provider.release_slot(listing.unit_id)
            raise

        logger.info(
            "booking_created",
            booking_id=saved.id,
            listing_id=listing.id,
            student_id=request.student_id,
            expires_at=expires_at,
        )
        return saved
