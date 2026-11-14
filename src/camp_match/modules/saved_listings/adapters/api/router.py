"""Saved listings API router."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from camp_match.modules.saved_listings.adapters.api import schemas
from camp_match.modules.saved_listings.adapters.api.dependencies import (
    get_list_saved_listings_use_case,
    get_save_listing_use_case,
    get_unsave_listing_use_case,
)
from camp_match.modules.saved_listings.application.ports.inbound import (
    ListSavedListingsQuery,
    SaveListingCommand,
    UnsaveListingCommand,
)
from camp_match.modules.saved_listings.application.use_cases.list_saved_listings import (
    ListSavedListingsUseCase,
)
from camp_match.modules.saved_listings.application.use_cases.save_listing import (
    SaveListingUseCase,
)
from camp_match.modules.saved_listings.application.use_cases.unsave_listing import (
    UnsaveListingUseCase,
)
from camp_match.platform.security.authentication import get_current_identity_id
from camp_match.shared_kernel.application.errors import ConflictError, NotFoundError
from camp_match.shared_kernel.application.pagination import PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/saved-listings", tags=["saved-listings"])


def _handle_error(e: Exception) -> None:
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=e.message) from e
    if isinstance(e, ConflictError):
        raise HTTPException(status_code=409, detail=e.message) from e
    if isinstance(e, ValueError):
        raise HTTPException(status_code=422, detail=str(e)) from e
    raise e


@router.post(
    "/{listing_id}",
    response_model=schemas.SaveListingResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def save_listing(
    listing_id: str,
    user_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[
        SaveListingUseCase, Depends(get_save_listing_use_case)
    ],
) -> schemas.SaveListingResponseSchema:
    try:
        lid = EntityId.from_string(listing_id)
        result = await use_case.execute(
            SaveListingCommand(user_id=user_id, listing_id=lid)
        )
        return schemas.SaveListingResponseSchema(
            listing_id=str(result.listing_id.value),
            saved_at=result.saved_at,
            already_saved=result.already_saved,
        )
    except Exception as e:
        _handle_error(e)
        raise


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_listing(
    listing_id: str,
    user_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[
        UnsaveListingUseCase, Depends(get_unsave_listing_use_case)
    ],
) -> None:
    try:
        lid = EntityId.from_string(listing_id)
        await use_case.execute(
            UnsaveListingCommand(user_id=user_id, listing_id=lid)
        )
    except Exception as e:
        _handle_error(e)


@router.get("", response_model=schemas.SavedListingPageSchema)
async def list_saved_listings(
    user_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[
        ListSavedListingsUseCase, Depends(get_list_saved_listings_use_case)
    ],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> schemas.SavedListingPageSchema:
    try:
        page_req = PageRequest(page=page, page_size=page_size)
        page_result = await use_case.execute(
            ListSavedListingsQuery(user_id=user_id, page_request=page_req)
        )
        items = [
            schemas.SavedListingItemSchema(
                listing_id=str(item.listing_id.value),
                saved_at=item.saved_at,
                availability=item.availability,
                listing=item.listing,
            )
            for item in page_result.items
        ]
        return schemas.SavedListingPageSchema(
            items=items,
            total=page_result.total,
            page=page_result.page,
            page_size=page_result.page_size,
        )
    except Exception as e:
        _handle_error(e)
        raise
