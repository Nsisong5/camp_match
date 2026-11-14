"""Housing events subscriber for booking module."""
from __future__ import annotations

import structlog
from typing import Any

from camp_match.modules.housing.application.ports.events import (
    ListingSuspended,
    ListingSuspensionLifted,
)
from camp_match.modules.booking.application.use_cases.invalidate_bookings_for_listing import (
    InvalidateBookingsForListingUseCase,
)
from camp_match.modules.booking.adapters.housing.housing_provider import (
    InProcessHousingProvider,
)
from camp_match.modules.housing.adapters.persistence.repository import (
    SqlAlchemyListingRepository,
    SqlAlchemyPropertyRepository,
    SqlAlchemyUnitRepository,
)

logger = structlog.get_logger(__name__)


def register_housing_subscribers(
    bus: Any,
    session_factory: Any,
    clock: Any,
    settings: Any,
) -> None:
    async def handle_listing_suspended(event: ListingSuspended) -> None:
        try:
            async with session_factory() as session:
                listing_repo = SqlAlchemyListingRepository(session)
                prop_repo = SqlAlchemyPropertyRepository(session)
                unit_repo = SqlAlchemyUnitRepository(session)
                housing_provider = InProcessHousingProvider(
                    listing_repo, prop_repo, unit_repo
                )

                reason_code = (
                    "OWNER_ACCOUNT_DISABLED"
                    if event.reason_code == "OWNER_ACCOUNT_DISABLED"
                    else "LISTING_SUSPENDED"
                )
                uc = InvalidateBookingsForListingUseCase(
                    session_factory, housing_provider, clock, settings
                )
                await uc(event.listing_id, reason_code, event.event_id)
        except Exception as e:
            logger.error(
                "housing_subscriber_listing_suspended_failed",
                error=str(e),
                event_id=event.event_id,
            )
            raise

    async def handle_listing_suspension_lifted(
        event: ListingSuspensionLifted,
    ) -> None:
        pass

    bus.subscribe(ListingSuspended, handle_listing_suspended)
    bus.subscribe(ListingSuspensionLifted, handle_listing_suspension_lifted)
