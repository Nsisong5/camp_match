from __future__ import annotations

import uuid

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.modules.housing.adapters.persistence.models import (
    ListingMediaModel,
    ListingModel,
    PropertyModel,
    UnitModel,
)
from camp_match.modules.housing.domain.entities import Listing, Property, Unit
from camp_match.modules.housing.domain.value_objects import (
    BillingPeriod,
    Coordinates,
    Currency,
    ListingStatus,
    Price,
    PropertyStatus,
    PropertyType,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class SqlAlchemyPropertyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, property: Property) -> None:
        model = PropertyModel(
            id=property.id.value,
            provider_id=property.provider_id.value,
            property_type=property.property_type.value,
            name=property.name,
            description=property.description,
            address=property.address,
            latitude=property.coordinates.latitude,
            longitude=property.coordinates.longitude,
            campus_id=property.campus_id.value if property.campus_id else None,
            has_water=property.has_water,
            has_electricity=property.has_electricity,
            has_security=property.has_security,
            has_parking=property.has_parking,
            has_generator=property.has_generator,
            has_cctv=property.has_cctv,
            has_wifi=property.has_wifi,
            status=property.status.value,
        )
        self._session.add(model)

    async def get_by_id(self, property_id: EntityId) -> Property | None:
        stmt = select(PropertyModel).where(PropertyModel.id == property_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_by_ids(self, property_ids: list[EntityId]) -> list[Property]:
        if not property_ids:
            return []
        uuids = [pid.value for pid in property_ids]
        stmt = select(PropertyModel).where(PropertyModel.id.in_(uuids))
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def update(self, property: Property) -> None:
        stmt = select(PropertyModel).where(PropertyModel.id == property.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            model.name = property.name
            model.description = property.description
            model.address = property.address
            model.latitude = property.coordinates.latitude
            model.longitude = property.coordinates.longitude
            model.campus_id = (
                property.campus_id.value if property.campus_id else None
            )
            model.has_water = property.has_water
            model.has_electricity = property.has_electricity
            model.has_security = property.has_security
            model.has_parking = property.has_parking
            model.has_generator = property.has_generator
            model.has_cctv = property.has_cctv
            model.has_wifi = property.has_wifi
            model.status = property.status.value

    def _to_domain(self, model: PropertyModel) -> Property:
        return Property(
            id=EntityId(model.id),
            provider_id=EntityId(model.provider_id),
            property_type=PropertyType(model.property_type),
            name=model.name,
            description=model.description,
            address=model.address,
            coordinates=Coordinates(
                latitude=float(model.latitude),
                longitude=float(model.longitude),
            ),
            campus_id=EntityId(model.campus_id) if model.campus_id else None,
            has_water=model.has_water,
            has_electricity=model.has_electricity,
            has_security=model.has_security,
            has_parking=model.has_parking,
            has_generator=model.has_generator,
            has_cctv=model.has_cctv,
            has_wifi=model.has_wifi,
            status=PropertyStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class SqlAlchemyUnitRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, unit: Unit) -> None:
        model = UnitModel(
            id=unit.id.value,
            property_id=unit.property_id.value,
            label=unit.label,
            total_capacity=unit.total_capacity,
            occupied_count=unit.occupied_count,
            is_furnished=unit.is_furnished,
            has_private_bathroom=unit.has_private_bathroom,
            has_kitchen=unit.has_kitchen,
        )
        self._session.add(model)

    async def get_by_id(self, unit_id: EntityId) -> Unit | None:
        stmt = select(UnitModel).where(UnitModel.id == unit_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_by_ids(self, unit_ids: list[EntityId]) -> list[Unit]:
        if not unit_ids:
            return []
        uuids = [uid.value for uid in unit_ids]
        stmt = select(UnitModel).where(UnitModel.id.in_(uuids))
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def update(self, unit: Unit) -> None:
        stmt = select(UnitModel).where(UnitModel.id == unit.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            model.label = unit.label
            model.total_capacity = unit.total_capacity
            model.occupied_count = unit.occupied_count
            model.is_furnished = unit.is_furnished
            model.has_private_bathroom = unit.has_private_bathroom
            model.has_kitchen = unit.has_kitchen

    async def increment_occupancy(self, unit_id: EntityId) -> bool:
        stmt = (
            update(UnitModel)
            .where(
                and_(
                    UnitModel.id == unit_id.value,
                    UnitModel.occupied_count < UnitModel.total_capacity,
                )
            )
            .values(occupied_count=UnitModel.occupied_count + 1)
        )
        res = await self._session.execute(stmt)
        return (res.rowcount or 0) > 0

    async def decrement_occupancy(self, unit_id: EntityId) -> bool:
        stmt = (
            update(UnitModel)
            .where(
                and_(
                    UnitModel.id == unit_id.value,
                    UnitModel.occupied_count > 0,
                )
            )
            .values(occupied_count=UnitModel.occupied_count - 1)
        )
        res = await self._session.execute(stmt)
        return (res.rowcount or 0) > 0

    async def try_reserve(self, unit_id: EntityId) -> bool:
        return await self.increment_occupancy(unit_id)

    async def try_release(self, unit_id: EntityId) -> bool:
        return await self.decrement_occupancy(unit_id)

    def _to_domain(self, model: UnitModel) -> Unit:
        return Unit(
            id=EntityId(model.id),
            property_id=EntityId(model.property_id),
            label=model.label,
            total_capacity=model.total_capacity,
            occupied_count=model.occupied_count,
            is_furnished=model.is_furnished,
            has_private_bathroom=model.has_private_bathroom,
            has_kitchen=model.has_kitchen,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class SqlAlchemyListingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, listing: Listing) -> None:
        model = ListingModel(
            id=listing.id.value,
            property_id=listing.property_id.value,
            unit_id=listing.unit_id.value,
            title=listing.title,
            description=listing.description,
            price_amount_kobo=listing.price.amount_kobo,
            price_currency=listing.price.currency.value,
            price_period=listing.price.period.value,
            status=listing.status.value,
            suspension_reference=listing.suspension_reference.value
            if listing.suspension_reference
            else None,
            suspension_reason=listing.suspension_reason,
        )
        self._session.add(model)

    async def get_by_id(self, listing_id: EntityId) -> Listing | None:
        stmt = select(ListingModel).where(ListingModel.id == listing_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_by_ids(self, listing_ids: list[EntityId]) -> list[Listing]:
        if not listing_ids:
            return []
        uuids = [lid.value for lid in listing_ids]
        stmt = select(ListingModel).where(ListingModel.id.in_(uuids))
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def update(self, listing: Listing) -> None:
        stmt = select(ListingModel).where(ListingModel.id == listing.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            model.title = listing.title
            model.description = listing.description
            model.price_amount_kobo = listing.price.amount_kobo
            model.status = listing.status.value
            model.suspension_reference = (
                listing.suspension_reference.value
                if listing.suspension_reference
                else None
            )
            model.suspension_reason = listing.suspension_reason

    async def get_by_unit_id(self, unit_id: EntityId) -> Listing | None:
        stmt = select(ListingModel).where(ListingModel.unit_id == unit_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def add_media(
        self,
        listing_id: EntityId,
        media_id: EntityId | None = None,
        media_url: str | None = None,
        display_order: int = 0,
    ) -> uuid.UUID:
        media_row_id = uuid.uuid4()
        model = ListingMediaModel(
            id=media_row_id,
            listing_id=listing_id.value,
            media_id=media_id.value if media_id else None,
            media_url=media_url,
            display_order=display_order,
        )
        self._session.add(model)
        await self._session.flush()
        return media_row_id

    async def get_media_for_listing(
        self, listing_id: EntityId
    ) -> list[ListingMediaModel]:
        stmt = (
            select(ListingMediaModel)
            .where(ListingMediaModel.listing_id == listing_id.value)
            .order_by(
                ListingMediaModel.display_order.asc(),
                ListingMediaModel.created_at.asc(),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active(
        self,
        campus_id: EntityId | None,
        property_type: PropertyType | None,
        page: PageRequest,
    ) -> Page[Listing]:
        stmt = (
            select(ListingModel)
            .join(UnitModel, ListingModel.unit_id == UnitModel.id)
            .join(PropertyModel, ListingModel.property_id == PropertyModel.id)
            .where(
                and_(
                    ListingModel.status == ListingStatus.PUBLISHED.value,
                    UnitModel.occupied_count < UnitModel.total_capacity,
                )
            )
        )

        if campus_id:
            stmt = stmt.where(PropertyModel.campus_id == campus_id.value)
        if property_type:
            stmt = stmt.where(
                PropertyModel.property_type == property_type.value
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self._session.execute(count_stmt)
        total = total_res.scalar_one()

        offset = (page.page - 1) * page.page_size
        stmt = stmt.offset(offset).limit(page.page_size)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        items = [self._to_domain(m) for m in models]
        return Page(
            items=items,
            total=total,
            page=page.page,
            page_size=page.page_size,
        )

    async def list_by_provider_and_status(
        self,
        provider_id: EntityId,
        statuses: list[str],
        limit: int,
    ) -> list[Listing]:
        stmt = (
            select(ListingModel)
            .join(PropertyModel, ListingModel.property_id == PropertyModel.id)
            .where(
                and_(
                    PropertyModel.provider_id == provider_id.value,
                    ListingModel.status.in_(statuses),
                )
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def list_suspended_by_provider_and_reason(
        self,
        provider_id: EntityId,
        reason: str,
        reference_id: EntityId,
        limit: int,
    ) -> list[Listing]:
        stmt = (
            select(ListingModel)
            .join(PropertyModel, ListingModel.property_id == PropertyModel.id)
            .where(
                and_(
                    PropertyModel.provider_id == provider_id.value,
                    ListingModel.status == ListingStatus.SUSPENDED.value,
                    ListingModel.suspension_reason == reason,
                    ListingModel.suspension_reference == reference_id.value,
                )
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def list_suspended_ids(
        self,
        limit: int,
        after_id: EntityId | None,
    ) -> list[EntityId]:
        stmt = (
            select(ListingModel.id)
            .where(ListingModel.status == ListingStatus.SUSPENDED.value)
            .order_by(ListingModel.created_at.asc())
            .limit(limit)
        )
        if after_id:
            stmt = stmt.where(ListingModel.id > after_id.value)
        result = await self._session.execute(stmt)
        return [EntityId(row) for row in result.scalars().all()]

    def _to_domain(self, model: ListingModel) -> Listing:
        return Listing(
            id=EntityId(model.id),
            property_id=EntityId(model.property_id),
            unit_id=EntityId(model.unit_id),
            title=model.title,
            description=model.description,
            price=Price(
                amount_kobo=model.price_amount_kobo,
                currency=Currency(model.price_currency),
                period=BillingPeriod(model.price_period),
            ),
            status=ListingStatus(model.status),
            suspension_reference=EntityId(model.suspension_reference)
            if model.suspension_reference
            else None,
            suspension_reason=model.suspension_reason,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
