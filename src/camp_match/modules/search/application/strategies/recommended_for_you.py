"""Recommended for you discovery strategy."""

from __future__ import annotations

from datetime import datetime

from camp_match.modules.search.application.ports.outbound import (
    HousingProvider,
    ProfileProvider,
    SavedStateProvider,
    UniversityLocationProvider,
    VerificationProvider,
)
from camp_match.modules.search.application.strategies.recently_added import (
    RecentlyAddedStrategy,
)
from camp_match.modules.search.domain.ranking import haversine_distance
from camp_match.modules.search.domain.value_objects import (
    ScoredCandidate,
    VerificationState,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class RecommendedForYouStrategy:
    def __init__(
        self,
        housing_provider: HousingProvider,
        profile_provider: ProfileProvider,
        university_location_provider: UniversityLocationProvider,
        verification_provider: VerificationProvider,
        recently_added: RecentlyAddedStrategy,
        saved_state_provider: SavedStateProvider | None = None,
    ) -> None:
        self._housing_provider = housing_provider
        self._profile_provider = profile_provider
        self._university_location_provider = university_location_provider
        self._verification_provider = verification_provider
        self._recently_added = recently_added
        self._saved_state_provider = saved_state_provider

    async def get_feed(
        self, viewer_id: EntityId | None, page_request: PageRequest
    ) -> Page[ScoredCandidate]:
        if viewer_id is None:
            return await self._recently_added.get_feed(viewer_id, page_request)

        prefs = await self._profile_provider.get_student_preferences(viewer_id)
        if prefs is None:
            return await self._recently_added.get_feed(viewer_id, page_request)

        uni_id = prefs.get("university_id")
        budget_min = prefs.get("budget_min")
        budget_max = prefs.get("budget_max")
        pref_acc_type = prefs.get("accommodation_type")

        main_campus_coords = None
        if uni_id:
            main_campus_coords = (
                await self._university_location_provider.get_main_campus_coordinates(
                    uni_id
                )
            )

        candidates = await self._housing_provider.list_eligible_candidates(
            None, pref_acc_type, budget_max
        )

        listing_ids = [c.listing_id for c in candidates]
        verif_states = await self._verification_provider.get_verification_states(
            listing_ids
        )

        scored_candidates = []
        for candidate in candidates:
            dist = None
            if (
                main_campus_coords is not None
                and candidate.coordinates is not None
            ):
                dist = haversine_distance(
                    candidate.coordinates, main_campus_coords
                )

            weights = {
                "preference": 0.40,
                "proximity": 0.20,
                "verification": 0.20,
                "freshness": 0.20,
            }

            active_factors = []
            has_prefs = (
                budget_min is not None
                or budget_max is not None
                or pref_acc_type is not None
            )
            if has_prefs:
                active_factors.append("preference")
            if (
                uni_id is not None
                and main_campus_coords is not None
                and dist is not None
            ):
                active_factors.append("proximity")
            active_factors.extend(["verification", "freshness"])

            total_weight = sum(weights[f] for f in active_factors)
            norm_weights = {
                f: weights[f] / total_weight for f in active_factors
            }

            score = 0.0

            if "preference" in norm_weights and has_prefs:
                pref_score = 1.0
                if (
                    pref_acc_type
                    and candidate.accommodation_type != pref_acc_type
                ):
                    pref_score -= 0.5
                if budget_max and candidate.price_amount_kobo > budget_max:
                    pref_score = 0.0
                score += max(0.0, pref_score) * norm_weights["preference"]

            if "proximity" in norm_weights and dist is not None:
                prox_score = max(0.0, 1.0 - dist / 10.0)
                score += prox_score * norm_weights["proximity"]

            state = verif_states.get(
                candidate.listing_id, VerificationState.UNKNOWN
            )
            verif_score = 1.0 if state == VerificationState.VERIFIED else 0.0
            score += verif_score * norm_weights["verification"]

            try:
                created_dt = datetime.fromisoformat(
                    candidate.created_at.replace("Z", "+00:00")
                )
                days_since = (datetime.now(created_dt.tzinfo) - created_dt).days
                fresh_score = max(0.0, 1.0 - days_since / 90.0)
            except Exception:
                fresh_score = 1.0
            score += fresh_score * norm_weights["freshness"]

            scored_candidates.append(
                ScoredCandidate(
                    candidate, score, distance_km=dist, verification_state=state
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
