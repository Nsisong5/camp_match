from __future__ import annotations

from camp_match.modules.booking.application.ports.outbound import (
    HousingProvider,
    ListingSummary,
)
from camp_match.modules.housing.application.ports.outbound import (
    ListingRepository,
    PropertyRepository,
    UnitRepository,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


class SqlAlchemyUnitAvailabilityAdapter:
    def __init__(self, unit_repo: UnitRepository) -> None:
        self._unit_repo = unit_repo

    async def check_availability(self, unit_id: EntityId) -> int:
        unit = await self._unit_repo.get_by_id(unit_id)
        if not unit:
            return 0
        return unit.available_count

    async def reserve_slot(self, unit_id: EntityId) -> bool:
        return await self._unit_repo.try_reserve(unit_id)

    async def release_slot(self, unit_id: EntityId) -> None:
        await self._unit_repo.try_release(unit_id)


class InProcessHousingProvider(HousingProvider):
    def __init__(
        self,
        listing_repo: ListingRepository,
        property_repo: PropertyRepository,
        unit_repo: UnitRepository,
    ) -> None:
        self._listing_repo = listing_repo
        self._property_repo = property_repo
        self._availability_port = SqlAlchemyUnitAvailabilityAdapter(unit_repo)

    async def get_listing(self, listing_id: EntityId) -> ListingSummary | None:
        listing = await self._listing_repo.get_by_id(listing_id)
        if not listing:
            return None
        return ListingSummary(
            id=listing.id,
            unit_id=listing.unit_id,
            property_id=listing.property_id,
            status=listing.status.value if hasattr(listing.status, "value") else str(listing.status),
            price_amount_kobo=listing.price.amount_kobo,
            price_currency=listing.price.currency.value if hasattr(listing.price.currency, "value") else str(listing.price.currency),
            price_period=listing.price.period.value if hasattr(listing.price.period, "value") else str(listing.price.period),
        )

    async def get_property_owner(self, property_id: EntityId) -> EntityId | None:
        prop = await self._property_repo.get_by_id(property_id)
        if not prop:
            return None
        return prop.provider_id

    async def check_availability(self, unit_id: EntityId) -> int:
        return await self._availability_port.check_availability(unit_id)

    async def reserve_slot(self, unit_id: EntityId) -> bool:
        return await self._availability_port.reserve_slot(unit_id)

    async def release_slot(self, unit_id: EntityId) -> None:
        await self._availability_port.release_slot(unit_id)
