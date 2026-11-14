"""Get listing cards use case (Housing module)."""

from __future__ import annotations

from typing import Any

from camp_match.modules.housing.application.ports.inbound import HousingListingCard
from camp_match.modules.housing.application.ports.outbound import (
    ListingRepository,
    PropertyRepository,
    UnitRepository,
)
from camp_match.modules.housing.domain.value_objects import ListingStatus
from camp_match.shared_kernel.domain.identifiers import EntityId


class GetListingCardsUseCase:
    def __init__(
        self,
        listing_repo: ListingRepository,
        property_repo: PropertyRepository,
        unit_repo: UnitRepository,
    ) -> None:
        self._listing_repo = listing_repo
        self._property_repo = property_repo
        self._unit_repo = unit_repo

    async def __call__(
        self, listing_ids: list[EntityId]
    ) -> dict[EntityId, HousingListingCard]:
        if len(listing_ids) > 100:
            raise ValueError("Cannot request more than 100 listing cards at once.")
        if not listing_ids:
            return {}

        listings = await self._listing_repo.list_by_ids(listing_ids)
        listing_map = {l.id: l for l in listings}

        prop_ids = {l.property_id for l in listings}
        unit_ids = {l.unit_id for l in listings}

        properties = (
            await self._property_repo.list_by_ids(list(prop_ids)) if prop_ids else []
        )
        prop_map = {p.id: p for p in properties}

        units = await self._unit_repo.list_by_ids(list(unit_ids)) if unit_ids else []
        unit_map = {u.id: u for u in units}

        result: dict[EntityId, HousingListingCard] = {}
        for lid in listing_ids:
            listing = listing_map.get(lid)
            if not listing or listing.status != ListingStatus.PUBLISHED:
                result[lid] = HousingListingCard(state="UNAVAILABLE", data=None)
                continue

            prop = prop_map.get(listing.property_id)
            unit = unit_map.get(listing.unit_id)
            if not prop or not unit:
                result[lid] = HousingListingCard(state="UNAVAILABLE", data=None)
                continue

            state = "AVAILABLE" if unit.available_count > 0 else "FULLY_BOOKED"

            media_records = await self._listing_repo.get_media_for_listing(listing.id)
            media_list = [
                {
                    "media_id": str(m.media_id)
                    if hasattr(m, "media_id") and m.media_id
                    else str(m.id),
                    "media_url": getattr(m, "media_url", None),
                    "display_order": getattr(m, "display_order", 0),
                }
                for m in media_records
            ]

            amenities_list = []
            if prop.has_water:
                amenities_list.append("WATER")
            if prop.has_electricity:
                amenities_list.append("ELECTRICITY")
            if prop.has_security:
                amenities_list.append("SECURITY")
            if prop.has_parking:
                amenities_list.append("PARKING")
            if prop.has_generator:
                amenities_list.append("GENERATOR")
            if prop.has_cctv:
                amenities_list.append("CCTV")
            if prop.has_wifi:
                amenities_list.append("WIFI")
            if unit.is_furnished:
                amenities_list.append("FURNISHED")
            if unit.has_private_bathroom:
                amenities_list.append("PRIVATE_BATHROOM")
            if unit.has_kitchen:
                amenities_list.append("KITCHEN")

            card_data: dict[str, Any] = {
                "listing_id": str(listing.id),
                "property_id": str(prop.id),
                "title": listing.title,
                "accommodation_type": prop.property_type.value,
                "price": {
                    "amount_kobo": listing.price.amount_kobo,
                    "currency": listing.price.currency.value,
                    "period": listing.price.period.value,
                },
                "location_summary": prop.address,
                "distance_km": None,
                "amenities": amenities_list,
                "available_count": unit.available_count,
                "verification_state": "UNKNOWN",
                "media": media_list,
            }
            result[lid] = HousingListingCard(state=state, data=card_data)

        return result
