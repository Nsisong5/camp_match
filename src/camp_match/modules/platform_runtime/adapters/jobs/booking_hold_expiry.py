from __future__ import annotations

from typing import Any

from camp_match.modules.booking.adapters.housing.housing_provider import (
    InProcessHousingProvider,
)
from camp_match.modules.booking.adapters.persistence.repository import (
    SqlAlchemyBookingRepository,
)
from camp_match.modules.booking.application.use_cases.expire_holds import (
    ExpireHoldsUseCase,
)
from camp_match.modules.housing.adapters.persistence.repository import (
    SqlAlchemyListingRepository,
    SqlAlchemyPropertyRepository,
    SqlAlchemyUnitRepository,
)
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork


def build_booking_hold_expiry_job(
    session_factory: Any,
    session: Any = None,
    clock: Any = None,
    settings: Any = None,
    event_bus: Any = None,
) -> Any:
    if clock is None and settings is None and session is not None and hasattr(session, "now"):
        clock = session
        from camp_match.config.settings import get_settings
        settings = get_settings()
    elif clock is None and settings is not None and session is not None and hasattr(session, "now"):
        clock = session

    if clock is None:
        from camp_match.platform.clock import get_clock
        clock = get_clock()
    if settings is None:
        from camp_match.config.settings import get_settings
        settings = get_settings()

    async def run() -> Any:
        async with session_factory() as db_session:
            booking_repo = SqlAlchemyBookingRepository(db_session)
            listing_repo = SqlAlchemyListingRepository(db_session)
            property_repo = SqlAlchemyPropertyRepository(db_session)
            unit_repo = SqlAlchemyUnitRepository(db_session)
            housing_provider = InProcessHousingProvider(
                listing_repo, property_repo, unit_repo
            )
            uow = SqlAlchemyUnitOfWork(db_session)
            use_case = ExpireHoldsUseCase(
                booking_repo, housing_provider, uow, clock, event_bus
            )
            return await use_case.execute()

    return run
