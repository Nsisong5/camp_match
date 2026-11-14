"""Reconcile suspended listing bookings use case."""
from __future__ import annotations

import structlog
from typing import Any

from camp_match.modules.booking.application.use_cases.invalidate_bookings_for_listing import (
    InvalidateBookingsForListingUseCase,
)
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger(__name__)


class ReconcileSuspendedListingBookingsUseCase:
    def __init__(
        self,
        session_factory: Any,
        housing_provider: Any,
        clock: Any,
        settings: Any,
    ) -> None:
        self.session_factory = session_factory
        self.housing_provider = housing_provider
        self.clock = clock
        self.settings = settings

    async def __call__(self, limit: int = 100) -> int:
        listing_ids = await self.housing_provider.list_suspended_listing_ids(
            limit, None
        )
        total_invalidated = 0
        invalidate_uc = InvalidateBookingsForListingUseCase(
            self.session_factory, self.housing_provider, self.clock, self.settings
        )

        for listing_id in listing_ids:
            reason = await self.housing_provider.get_listing_suspension_reason(
                listing_id
            )
            reason_code = (
                "OWNER_ACCOUNT_DISABLED"
                if reason == "OWNER_ACCOUNT_DISABLED"
                else "LISTING_SUSPENDED"
            )
            count = await invalidate_uc(listing_id, reason_code, EntityId.new())
            total_invalidated += count

        return total_invalidated
