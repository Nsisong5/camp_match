"""Suspended listing reconcile job factory."""
from __future__ import annotations

from typing import Any

from camp_match.modules.booking.adapters.housing.housing_provider import (
    InProcessHousingProvider,
)
from camp_match.modules.booking.application.use_cases.reconcile_suspended_listing_bookings import (
    ReconcileSuspendedListingBookingsUseCase,
)
from camp_match.modules.housing.adapters.persistence.repository import (
    SqlAlchemyListingRepository,
    SqlAlchemyPropertyRepository,
    SqlAlchemyUnitRepository,
)


def build_suspended_listing_reconcile_job(
    session_factory: Any,
    session: Any = None,
    clock: Any = None,
    settings: Any = None,
    event_bus: Any = None,
) -> Any:
    if clock is None and settings is None and session is not None and not hasattr(session, "execute"):
        clock = session
    if settings is None:
        from camp_match.config.settings import get_settings
        settings = get_settings()
    if clock is None:
        from camp_match.platform.clock import get_clock
        clock = get_clock()
    async def run() -> int:
        async with session_factory() as session:
            listing_repo = SqlAlchemyListingRepository(session)
            prop_repo = SqlAlchemyPropertyRepository(session)
            unit_repo = SqlAlchemyUnitRepository(session)
            housing_provider = InProcessHousingProvider(
                listing_repo, prop_repo, unit_repo
            )
        uc = ReconcileSuspendedListingBookingsUseCase(
            session_factory, housing_provider, clock, settings
        )
        return await uc()

    return run
