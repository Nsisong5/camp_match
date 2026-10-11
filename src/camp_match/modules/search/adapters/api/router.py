from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from camp_match.modules.search.adapters.api import dependencies, schemas
from camp_match.modules.search.adapters.api.schemas import SearchRequestSchema, ScoredCandidateResponse, SearchPageSchema
from camp_match.modules.search.application.use_cases.search_listings import SearchListings
from camp_match.modules.search.application.use_cases.get_discovery_feed import GetDiscoveryFeed
from camp_match.modules.search.domain.value_objects import SearchCriteria
from camp_match.modules.identity.adapters.api.dependencies import get_auth_session
from camp_match.modules.identity.adapters.security.jwt_session import JwtAuthenticationSessionAdapter
from camp_match.shared_kernel.application.pagination import PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/search", tags=["search"])
security_scheme = HTTPBearer(auto_error=False)


async def get_current_identity_id_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
    auth: Annotated[JwtAuthenticationSessionAdapter, Depends(get_auth_session)] = ...,  # type: ignore
) -> EntityId | None:
    if not credentials or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        return None
    try:
        return await auth.decode_access_token(credentials.credentials)
    except Exception:
        return None


@router.get("/listings", response_model=SearchPageSchema)
async def search_listings(
    request: SearchRequestSchema = Depends(),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    use_case: SearchListings = Depends(dependencies.get_search_listings_use_case),
):
    campus_entity_id = EntityId.from_string(request.campus_id) if request.campus_id else None
    criteria = SearchCriteria(
        campus_id=campus_entity_id,
        min_price_kobo=request.min_price_kobo,
        max_price_kobo=request.max_price_kobo,
        billing_period=request.billing_period,
        accommodation_type=request.accommodation_type,
        amenities=frozenset(request.amenities),
        max_distance_km=request.max_distance_km,
        verified_only=request.verified_only,
        sort_by=request.sort_by,
    )
    page_req = PageRequest(page=page, page_size=page_size)
    page_result = await use_case.execute(criteria, page_req)

    response_items = []
    for sc in page_result.items:
        cand = sc.listing
        media_res = [
            {
                "media_id": m.get("media_id", ""),
                "media_url": m.get("media_url"),
                "display_order": m.get("display_order", 0),
            }
            for m in cand.media
        ]
        listing_resp = schemas.CandidateListingResponse(
            listing_id=str(cand.listing_id.value),
            property_id=str(cand.property_id.value),
            title=cand.title,
            accommodation_type=cand.accommodation_type,
            price_amount_kobo=cand.price_amount_kobo,
            price_currency=cand.price_currency,
            price_period=cand.price_period,
            available_count=cand.available_count,
            media=media_res,
        )
        response_items.append(
            schemas.ScoredCandidateResponse(
                listing=listing_resp,
                score=sc.score,
                distance_km=sc.distance_km,
                verification_state=sc.verification_state,
            )
        )
    return schemas.SearchPageSchema(
        items=response_items,
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
    )


@router.get("/discovery/{strategy_type}", response_model=SearchPageSchema)
async def get_discovery_feed(
    strategy_type: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    identity_id: Annotated[EntityId | None, Depends(get_current_identity_id_optional)] = None,
    use_case: GetDiscoveryFeed = Depends(dependencies.get_discovery_feed_use_case),
):
    page_req = PageRequest(page=page, page_size=page_size)
    try:
        page_result = await use_case.execute(identity_id, strategy_type, page_req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    response_items = []
    for sc in page_result.items:
        cand = sc.listing
        media_res = [
            {
                "media_id": m.get("media_id", ""),
                "media_url": m.get("media_url"),
                "display_order": m.get("display_order", 0),
            }
            for m in cand.media
        ]
        listing_resp = schemas.CandidateListingResponse(
            listing_id=str(cand.listing_id.value),
            property_id=str(cand.property_id.value),
            title=cand.title,
            accommodation_type=cand.accommodation_type,
            price_amount_kobo=cand.price_amount_kobo,
            price_currency=cand.price_currency,
            price_period=cand.price_period,
            available_count=cand.available_count,
            media=media_res,
        )
        response_items.append(
            schemas.ScoredCandidateResponse(
                listing=listing_resp,
                score=sc.score,
                distance_km=sc.distance_km,
                verification_state=sc.verification_state,
            )
        )
    return schemas.SearchPageSchema(
        items=response_items,
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
    )
