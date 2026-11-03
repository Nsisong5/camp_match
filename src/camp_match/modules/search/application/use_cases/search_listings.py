from datetime import datetime

from camp_match.modules.search.application.ports.outbound import (
    HousingProvider,
    UniversityLocationProvider,
    VerificationProvider,
)
from camp_match.modules.search.application.use_cases.apply_filters import apply_filters
from camp_match.modules.search.domain.ranking import SearchRankingStrategy
from camp_match.modules.search.domain.value_objects import (
    Coordinates,
    ScoredCandidate,
    SearchCriteria,
    SortOption,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest


class SearchListings:
    def __init__(
        self,
        housing_provider: HousingProvider,
        university_location_provider: UniversityLocationProvider,
        verification_provider: VerificationProvider,
        ranking_strategy: SearchRankingStrategy,
    ):
        self._housing_provider = housing_provider
        self._university_location_provider = university_location_provider
        self._verification_provider = verification_provider
        self._ranking_strategy = ranking_strategy

    async def execute(
        self, criteria: SearchCriteria, page_request: PageRequest
    ) -> Page[ScoredCandidate]:
        # 1. Fetch from Housing
        candidates = await self._housing_provider.list_eligible_candidates(
            criteria.campus_id, criteria.accommodation_type, criteria.max_price_kobo
        )

        # 2. Resolve coordinates if campus_id set
        campus_coords: Coordinates | None = None
        if criteria.campus_id:
            campus_coords = await self._university_location_provider.get_campus_coordinates(
                criteria.campus_id
            )

        # 3. Resolve verification
        listing_ids = [c.listing_id for c in candidates]
        verif_states = await self._verification_provider.get_verification_states(listing_ids)

        # 4. Apply fine filters
        filtered_candidates = apply_filters(
            candidates, criteria, verif_states, campus_coords=campus_coords
        )

        # 5. Rank / Sort
        scored = await self._ranking_strategy.score(
            filtered_candidates, criteria, verif_states, campus_coordinates=campus_coords
        )

        if criteria.sort_by != SortOption.RELEVANCE:

            def sort_key(sc: ScoredCandidate) -> tuple:
                created_dt = datetime.fromisoformat(sc.listing.created_at.replace("Z", "+00:00"))
                inverted_ts = -created_dt.timestamp()
                listing_id_val = sc.listing.listing_id.value

                if criteria.sort_by == SortOption.PRICE_ASC:
                    return (sc.listing.price_amount_kobo, inverted_ts, listing_id_val)
                if criteria.sort_by == SortOption.PRICE_DESC:
                    return (-sc.listing.price_amount_kobo, inverted_ts, listing_id_val)
                if criteria.sort_by == SortOption.DISTANCE:
                    dist = sc.distance_km if sc.distance_km is not None else float("inf")
                    return (dist, inverted_ts, listing_id_val)
                if criteria.sort_by == SortOption.NEWEST:
                    return (inverted_ts, listing_id_val)
                return (-sc.score, inverted_ts, listing_id_val)

            scored = sorted(scored, key=sort_key)

        # 6. Paginate and return
        total = len(scored)
        start = (page_request.page - 1) * page_request.page_size
        end = start + page_request.page_size
        items = scored[start:end]

        return Page(
            items=items,
            total=total,
            page=page_request.page,
            page_size=page_request.page_size,
        )
