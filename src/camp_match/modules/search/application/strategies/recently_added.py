"""Recently added discovery strategy."""

from __future__ import annotations

from datetime import datetime

from camp_match.modules.search.application.ports.outbound import (
    HousingProvider,
    SavedStateProvider,
    VerificationProvider,
)
from camp_match.modules.search.domain.value_objects import (
    ScoredCandidate,
    VerificationState,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class RecentlyAddedStrategy:
    def __init__(
        self,
        housing_provider: HousingProvider,
        verification_provider: VerificationProvider,
        saved_state_provider: SavedStateProvider | None = None,
    ) -> None:
        self._housing_provider = housing_provider
        self._verification_provider = verification_provider
        self._saved_state_provider = saved_state_provider

    async def get_feed(
        self, viewer_id: EntityId | None, page_request: PageRequest
    ) -> Page[ScoredCandidate]:
        candidates = await self._housing_provider.list_eligible_candidates(
            None, None, None
        )
        listing_ids = [c.listing_id for c in candidates]
        verif_states = await self._verification_provider.get_verification_states(
            listing_ids
        )

        scored_candidates = []
        for candidate in candidates:
            state = verif_states.get(candidate.listing_id, VerificationState.UNKNOWN)
            verif_score = 1.0 if state == VerificationState.VERIFIED else 0.0
            try:
                created_dt = datetime.fromisoformat(
                    candidate.created_at.replace("Z", "+00:00")
                )
                days_since = (datetime.now(created_dt.tzinfo) - created_dt).days
                fresh_score = max(0.0, 1.0 - days_since / 90.0)
            except Exception:
                fresh_score = 1.0

            score = 0.5 * verif_score + 0.5 * fresh_score
            scored_candidates.append(
                ScoredCandidate(
                    candidate, score, distance_km=None, verification_state=state
                )
            )

        def sort_key(sc: ScoredCandidate):
            try:
                created_dt = datetime.fromisoformat(
                    sc.listing.created_at.replace("Z", "+00:00")
                )
                ts = created_dt.timestamp()
            except Exception:
                ts = 0.0
            return (-sc.score, -ts, sc.listing.listing_id.value)

        sorted_scored = sorted(scored_candidates, key=sort_key)
        total = len(sorted_scored)
        start = (page_request.page - 1) * page_request.page_size
        end = start + page_request.page_size
        items = sorted_scored[start:end]

        page_listing_ids = [item.listing.listing_id for item in items]
        saved_ids = (
            await self._saved_state_provider.get_saved_state(
                viewer_id, page_listing_ids
            )
            if self._saved_state_provider and viewer_id is not None
            else set()
        )

        decorated_items = [
            ScoredCandidate(
                listing=item.listing,
                score=item.score,
                distance_km=item.distance_km,
                verification_state=item.verification_state,
                is_saved=(item.listing.listing_id in saved_ids),
            )
            for item in items
        ]

        return Page(
            items=decorated_items,
            total=total,
            page=page_request.page,
            page_size=page_request.page_size,
        )
