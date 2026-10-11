#!/usr/bin/env python3
from __future__ import annotations

import asyncio

from camp_match.config.settings import get_settings
from camp_match.modules.booking.adapters.housing.housing_provider import InProcessHousingProvider
from camp_match.modules.booking.adapters.persistence.repository import SqlAlchemyBookingRepository
from camp_match.modules.booking.application.use_cases.expire_holds import ExpireHoldsUseCase
from camp_match.modules.housing.adapters.persistence.repository import (
    SqlAlchemyListingRepository,
    SqlAlchemyPropertyRepository,
    SqlAlchemyUnitRepository,
)
from camp_match.platform.clock import get_clock
from camp_match.platform.db.session import create_engine, create_session_factory
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork


async def expire_holds_main() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        booking_repo = SqlAlchemyBookingRepository(session)
        listing_repo = SqlAlchemyListingRepository(session)
        property_repo = SqlAlchemyPropertyRepository(session)
        unit_repo = SqlAlchemyUnitRepository(session)
        housing_provider = InProcessHousingProvider(listing_repo, property_repo, unit_repo)
        uow = SqlAlchemyUnitOfWork(session)
        clock = get_clock()

        use_case = ExpireHoldsUseCase(booking_repo, housing_provider, uow, clock)
        result = await use_case.execute()
        print(f"Expired holds processed successfully. Count: {result.expired_count}")

    await engine.dispose()


def main() -> None:
    asyncio.run(expire_holds_main())


if __name__ == "__main__":
    main()
