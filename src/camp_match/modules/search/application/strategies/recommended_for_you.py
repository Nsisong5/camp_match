from datetime import datetime, timezone
from camp_match.modules.search.application.strategies.discovery_strategy import DiscoveryStrategy
from camp_match.modules.search.application.strategies.recently_added import RecentlyAddedStrategy
from camp_match.modules.search.domain.value_objects import ScoredCandidate, CandidateListing, VerificationState, Coordinates
from camp_match.modules.search.domain.ranking import haversine_distance
from camp_match.shared_kernel.domain.identifiers import EntityId
from camp_match.shared_kernel.application.pagination import Page, PageRequest


class RecommendedForYouStrategy:
    def __init__(
        self,
        housing_provider,
        profile_provider,
        university_location_provider,
        verification_provider,
        recently_added: RecentlyAddedStrategy,
    ) -> None:
        self._housing_provider = housing_provider
        self._profile_provider = profile_provider
        self._university_location_provider = university_location_provider
        self._verification_provider = verification_provider
        self._recently_added = recently_added

    async def get_feed(self, identity_id: EntityId | None, page_request: PageRequest) -> Page[ScoredCandidate]:
        if identity_id is None:
            return await self._recently_added.get_feed(identity_id, page_request)

        prefs = await self._profile_provider.get_student_preferences(identity_id)
        if prefs is None:
            return await self._recently_added.get_feed(identity_id, page_request)

        uni_id = prefs.get("university_id")
        budget_min = prefs.get("budget_min")
        budget_max = prefs.get("budget_max")
        pref_acc_type = prefs.get("accommodation_type")

        # 1. Get main campus coordinates if university_id is set (once per request)
        main_campus_coords = None
        if uni_id:
            main_campus_coords = await self._university_location_provider.get_main_campus_coordinates(uni_id)

        # 2. Fetch candidates from housing
        candidates = await self._housing_provider.list_eligible_candidates(
            None, pref_acc_type, budget_max
        )

        # 3. Fetch verification states
        listing_ids = [c.listing_id for c in candidates]
        verif_states = await self._verification_provider.get_verification_states(listing_ids)

        # 4. Score candidates
        scored_candidates = []
        for candidate in candidates:
            dist = None
            if main_campus_coords is not None and candidate.coordinates is not None:
                dist = haversine_distance(candidate.coordinates, main_campus_coords)

            # Factors and weights (ADR-091)
            weights = {
                "preference": 0.40,
                "proximity": 0.20,
                "verification": 0.20,
                "freshness": 0.20,
            }

            active_factors = []
            has_prefs = (budget_min is not None or budget_max is not None or pref_acc_type is not None)
            if has_prefs:
                active_factors.append("preference")
            if uni_id is not None and main_campus_coords is not None and dist is not None:
                active_factors.append("proximity")
            active_factors.extend(["verification", "freshness"])

            total_weight = sum(weights[f] for f in active_factors)
            norm_weights = {f: weights[f] / total_weight for f in active_factors}

            score = 0.0

            # Preference match score
            if "preference" in norm_weights and has_prefs:
                pref_score = 1.0
                if pref_acc_type and candidate.accommodation_type != pref_acc_type:
                    pref_score -= 0.5
                if budget_max and candidate.price_amount_kobo > budget_max:
                    pref_score = 0.0
                score += max(0.0, pref_score) * norm_weights["preference"]

            # Proximity score
            if "proximity" in norm_weights and dist is not None:
                prox_score = max(0.0, 1.0 - dist / 10.0)
                score += prox_score * norm_weights["proximity"]

            # Verification score
            state = verif_states.get(candidate.listing_id, VerificationState.UNKNOWN)
            verif_score = 1.0 if state == VerificationState.VERIFIED else 0.0
            score += verif_score * norm_weights["verification"]

            # Freshness score
            try:
                created_dt = datetime.fromisoformat(candidate.created_at.replace("Z", "+00:00"))
                days_since = (datetime.now(created_dt.tzinfo) - created_dt).days
                fresh_score = max(0.0, 1.0 - days_since / 90.0)
            except Exception:
                fresh_score = 1.0
            score += fresh_score * norm_weights["freshness"]

            scored_candidates.append(ScoredCandidate(candidate, score, distance_km=dist, verification_state=state))

        # Sort: score desc, created desc, id asc
        def sort_key(sc: ScoredCandidate):
            try:
                created_dt = datetime.fromisoformat(sc.listing.created_at.replace("Z", "+00:00"))
                ts = created_dt.timestamp()
            except Exception:
                ts = 0.0
            return (-sc.score, -ts, sc.listing.listing_id.value)

        sorted_scored = sorted(scored_candidates, key=sort_key)

        total = len(sorted_scored)
        start = (page_request.page - 1) * page_request.page_size
        end = start + page_request.page_size
        items = sorted_scored[start:end]

        return Page(
            items=items,
            total=total,
            page=page_request.page,
            page_size=page_request.page_size,
        )
