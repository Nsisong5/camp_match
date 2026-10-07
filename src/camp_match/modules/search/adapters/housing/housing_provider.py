from __future__ import annotations

from camp_match.modules.search.application.ports.outbound import HousingProvider
from camp_match.modules.housing.application.ports.outbound import (
    ListingRepository,
    PropertyRepository,
    UnitRepository,
)
from camp_match.modules.search.domain.value_objects import (
    CandidateListing,
    Coordinates,
    AccommodationType,
    BillingPeriod,
    Amenity,
)
from camp_match.shared_kernel.domain.identifiers import EntityId
from camp_match.shared_kernel.application.pagination import PageRequest


class HousingProviderAdapter(HousingProvider):
    def __init__(
        self,
        listing_repo: ListingRepository,
        property_repo: PropertyRepository,
        unit_repo: UnitRepository,
    ):
        self._listing_repo = listing_repo
        self._property_repo = property_repo
        self._unit_repo = unit_repo

    async def list_eligible_candidates(
        self,
        campus_id: EntityId | None,
        accommodation_type: AccommodationType | None,
        max_price_kobo: int | None,
    ) -> list[CandidateListing]:
        prop_type = None
        if accommodation_type:
            from camp_match.modules.housing.domain.value_objects import PropertyType
            try:
                prop_type = PropertyType(accommodation_type.value)
            except ValueError:
                pass

        page_res = await self._listing_repo.list_active(
            campus_id=campus_id,
            property_type=prop_type,
            page=PageRequest(page=1, page_size=100),
        )

        candidates = []
        for listing in page_res.items:
            if max_price_kobo is not None and listing.price.amount_kobo > max_price_kobo:
                continue

            prop = await self._property_repo.get_by_id(listing.property_id)
            unit = await self._unit_repo.get_by_id(listing.unit_id)
            if not prop or not unit:
                continue

            media_records = await self._listing_repo.get_media_for_listing(listing.id)
            media_list = [
                {
                    "media_id": str(m.media_id) if hasattr(m, "media_id") and m.media_id else str(m.id),
                    "media_url": getattr(m, "media_url", None),
                    "display_order": getattr(m, "display_order", 0),
                }
                for m in media_records
            ]

            amenities_set = set()
            if prop.has_water:
                amenities_set.add(Amenity.WATER)
            if prop.has_electricity:
                amenities_set.add(Amenity.ELECTRICITY)
            if prop.has_security:
                amenities_set.add(Amenity.SECURITY)
            if prop.has_parking:
                amenities_set.add(Amenity.PARKING)
            if prop.has_generator:
                amenities_set.add(Amenity.GENERATOR)
            if prop.has_cctv:
                amenities_set.add(Amenity.CCTV)
            if prop.has_wifi:
                amenities_set.add(Amenity.WIFI)
            if unit.is_furnished:
                amenities_set.add(Amenity.FURNISHED)
            if unit.has_private_bathroom:
                amenities_set.add(Amenity.PRIVATE_BATHROOM)
            if unit.has_kitchen:
                amenities_set.add(Amenity.KITCHEN)

            acc_type = AccommodationType(prop.property_type.value)
            billing_per = BillingPeriod(listing.price.period.value)

            candidate = CandidateListing(
                listing_id=listing.id,
                property_id=prop.id,
                title=listing.title,
                accommodation_type=acc_type,
                price_amount_kobo=listing.price.amount_kobo,
                price_currency=listing.price.currency.value,
                price_period=billing_per,
                coordinates=Coordinates(
                    latitude=prop.coordinates.latitude,
                    longitude=prop.coordinates.longitude,
                ),
                campus_id=prop.campus_id,
                amenities=frozenset(amenities_set),
                available_count=unit.available_count,
                created_at=listing.created_at.isoformat(),
                media=media_list,
            )
            candidates.append(candidate)

        return candidates
