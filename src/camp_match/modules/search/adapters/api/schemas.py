
from pydantic import BaseModel, Field

from camp_match.modules.search.domain.value_objects import (
    AccommodationType,
    Amenity,
    BillingPeriod,
    SortOption,
    VerificationState,
)


class SearchRequestSchema(BaseModel):
    campus_id: str | None = None
    min_price_kobo: int | None = Field(None, ge=0)
    max_price_kobo: int | None = Field(None, ge=0)
    billing_period: BillingPeriod | None = None
    accommodation_type: AccommodationType | None = None
    amenities: list[Amenity] = []
    max_distance_km: float | None = Field(None, gt=0)
    verified_only: bool = False
    sort_by: SortOption = SortOption.RELEVANCE

class CandidateListingResponse(BaseModel):
    listing_id: str
    property_id: str
    title: str
    accommodation_type: AccommodationType
    price_amount_kobo: int
    price_currency: str
    price_period: BillingPeriod
    available_count: int
    media: list[dict] = []

class ScoredCandidateResponse(BaseModel):
    listing: CandidateListingResponse
    score: float
    distance_km: float | None = None
    verification_state: VerificationState = VerificationState.UNKNOWN


class SearchPageSchema(BaseModel):
    items: list[ScoredCandidateResponse]
    total: int
    page: int
    page_size: int
