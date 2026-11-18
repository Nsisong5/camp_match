"""Transaction context provider adapter."""
from __future__ import annotations

import importlib
import structlog
from typing import Any
from uuid import UUID

from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class TransactionContextProvider:
    def __init__(self, session: Any) -> None:
        self._session = session

    async def get_context(
        self,
        student_id: EntityId,
        provider_id: EntityId | None,
        listing_id: EntityId | None,
        property_id: EntityId | None,
        booking_id: EntityId,
    ) -> dict[str, Any]:
        status = "AVAILABLE"
        student_name: str | None = None
        provider_name: str | None = None
        listing_title: str | None = None
        property_name: str | None = None
        booking_status: str | None = None
        handover_offered_at: Any = None
        handover_accepted_at: Any = None
        student_confirmed: bool = False

        try:
            profile_repo_mod = importlib.import_module(
                "camp_match.modules.profile.adapters.persistence.repository"
            )
            profile_repo = profile_repo_mod.SqlAlchemyProfileRepository(self._session)
            
            student_profile = await profile_repo.get_by_identity_id(student_id)
            if student_profile:
                student_name = student_profile.display_name

            if provider_id:
                provider_profile = await profile_repo.get_by_identity_id(provider_id)
                if provider_profile:
                    provider_name = provider_profile.display_name
        except Exception as e:
            logger.warning("transaction_context_profile_failed", error=str(e))
            status = "PARTIAL"

        try:
            housing_repo_mod = importlib.import_module(
                "camp_match.modules.housing.adapters.persistence.repository"
            )
            listing_repo = housing_repo_mod.SqlAlchemyListingRepository(self._session)
            property_repo = housing_repo_mod.SqlAlchemyPropertyRepository(self._session)

            if listing_id:
                listing = await listing_repo.get_by_id(listing_id)
                if listing:
                    listing_title = getattr(listing, "title", None)

            if property_id:
                prop = await property_repo.get_by_id(property_id)
                if prop:
                    property_name = getattr(prop, "name", None)
        except Exception as e:
            logger.warning("transaction_context_housing_failed", error=str(e))
            status = "PARTIAL"

        try:
            booking_repo_mod = importlib.import_module(
                "camp_match.modules.booking.adapters.persistence.repository"
            )
            booking_repo = booking_repo_mod.SqlAlchemyBookingRepository(self._session)
            booking = await booking_repo.get_by_id(booking_id)
            if booking:
                booking_status = booking.status.value if hasattr(booking.status, "value") else str(booking.status)
                handover_offered_at = getattr(booking, "handover_offered_at", None)
                handover_accepted_at = getattr(booking, "handover_accepted_at", None)
                student_confirmed = getattr(booking, "student_confirmed", False) or (handover_accepted_at is not None)
        except Exception as e:
            logger.warning("transaction_context_booking_failed", error=str(e))
            status = "UNAVAILABLE"

        return {
            "context_status": status,
            "parties": {
                "student": {"id": str(student_id.value), "display_name": student_name},
                "provider": {"id": str(provider_id.value) if provider_id else None, "display_name": provider_name},
            },
            "listing": {
                "listing_id": str(listing_id.value) if listing_id else None,
                "property_id": str(property_id.value) if property_id else None,
                "title": listing_title,
                "property_name": property_name,
            },
            "booking": {
                "id": str(booking_id.value),
                "status": booking_status or "UNKNOWN",
                "handover": {
                    "offered_at": handover_offered_at,
                    "accepted_at": handover_accepted_at,
                    "student_confirmed": student_confirmed,
                },
            },
        }
