"""Review router adapter."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from camp_match.modules.payment.adapters.api import dependencies, review_schemas
from camp_match.modules.payment.application.use_cases.get_transaction_review import (
    GetTransactionReviewRequest,
    GetTransactionReviewUseCase,
)
from camp_match.modules.payment.application.use_cases.get_transaction_review_summary import (
    GetTransactionReviewSummaryRequest,
    GetTransactionReviewSummaryUseCase,
)
from camp_match.modules.payment.application.use_cases.list_transaction_reviews import (
    ListTransactionReviewsRequest,
    ListTransactionReviewsUseCase,
)
from camp_match.platform.security.authentication import get_current_identity_id
from camp_match.shared_kernel.application.errors import NotFoundError
from camp_match.shared_kernel.application.pagination import PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/payments/review", tags=["Payment Review"])


@router.get("/transactions", response_model=review_schemas.PageSchema[review_schemas.TransactionReviewListItemSchema])
async def list_transaction_reviews(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[ListTransactionReviewsUseCase, Depends(dependencies.get_list_transaction_reviews_use_case)],
    stage: list[str] | None = Query(None),
    next_action: str | None = Query(None),
    needs_action: bool | None = Query(None),
    booking_id: UUID | None = Query(None),
    student_id: UUID | None = Query(None),
    provider_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> review_schemas.PageSchema[review_schemas.TransactionReviewListItemSchema]:
    request = ListTransactionReviewsRequest(
        actor_id=actor_id,
        page_request=PageRequest(page=page, page_size=page_size),
        stages=stage,
        next_action=next_action,
        needs_action=needs_action,
        booking_id=EntityId(booking_id) if booking_id else None,
        student_id=EntityId(student_id) if student_id else None,
        provider_id=EntityId(provider_id) if provider_id else None,
    )
    paged = await use_case.execute(request)
    return review_schemas.PageSchema(
        items=[
            review_schemas.TransactionReviewListItemSchema(
                payment_id=item.payment_id,
                booking_id=item.booking_id,
                student_id=item.student_id,
                provider_id=item.provider_id,
                amount_kobo=item.amount_kobo,
                currency=item.currency,
                paid_at=item.paid_at,
                stage=item.stage,
                next_action=item.next_action,
                next_action_since=item.next_action_since,
                released_kobo=item.released_kobo,
                refunded_kobo=item.refunded_kobo,
                warnings_sent=item.warnings_sent,
                warnings_required=item.warnings_required,
                open_dispute=bool(item.open_dispute_id),
                can_release=item.next_action == "RELEASE_FUNDS", # Simplified
            )
            for item in paged.items
        ],
        total=paged.total,
        page=paged.page,
        page_size=paged.page_size,
    )


@router.get("/summary", response_model=review_schemas.TransactionReviewSummarySchema)
async def get_transaction_review_summary(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[GetTransactionReviewSummaryUseCase, Depends(dependencies.get_get_transaction_review_summary_use_case)],
) -> review_schemas.TransactionReviewSummarySchema:
    result = await use_case.execute(GetTransactionReviewSummaryRequest(actor_id=actor_id))
    return review_schemas.TransactionReviewSummarySchema(**result)


@router.get("/transactions/{payment_id}", response_model=review_schemas.TransactionReviewDetailSchema)
async def get_transaction_review(
    payment_id: UUID,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[GetTransactionReviewUseCase, Depends(dependencies.get_get_transaction_review_use_case)],
) -> review_schemas.TransactionReviewDetailSchema:
    try:
        result = await use_case.execute(
            GetTransactionReviewRequest(actor_id=actor_id, payment_id=EntityId(payment_id))
        )
        return review_schemas.TransactionReviewDetailSchema(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/transactions/by-booking/{booking_id}", response_model=review_schemas.TransactionReviewDetailSchema)
async def get_transaction_review_by_booking(
    booking_id: UUID,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[GetTransactionReviewUseCase, Depends(dependencies.get_get_transaction_review_use_case)],
) -> review_schemas.TransactionReviewDetailSchema:
    try:
        result = await use_case.execute(
            GetTransactionReviewRequest(actor_id=actor_id, booking_id=EntityId(booking_id))
        )
        return review_schemas.TransactionReviewDetailSchema(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
