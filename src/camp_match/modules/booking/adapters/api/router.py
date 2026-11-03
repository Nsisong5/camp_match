from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from camp_match.modules.booking.adapters.api import dependencies, schemas
from camp_match.modules.booking.application.ports.inbound import (
    CancelBookingRequest,
    ConfirmBookingRequest,
    ConfirmHandoverAcceptedRequest,
    ConfirmHandoverOfferedRequest,
    CreateBookingRequest,
    GetBookingRequest,
    ListBookingsForPropertyRequest,
    ListMyBookingsRequest,
)
from camp_match.modules.booking.application.use_cases.cancel_booking import CancelBookingUseCase
from camp_match.modules.booking.application.use_cases.confirm_booking import ConfirmBookingUseCase
from camp_match.modules.booking.application.use_cases.confirm_handover_accepted import (
    ConfirmHandoverAcceptedUseCase,
)
from camp_match.modules.booking.application.use_cases.confirm_handover_offered import (
    ConfirmHandoverOfferedUseCase,
)
from camp_match.modules.booking.application.use_cases.create_booking import CreateBookingUseCase
from camp_match.modules.booking.application.use_cases.get_booking import GetBookingUseCase
from camp_match.modules.booking.application.use_cases.list_bookings_for_property import (
    ListBookingsForPropertyUseCase,
)
from camp_match.modules.booking.application.use_cases.list_my_bookings import ListMyBookingsUseCase
from camp_match.platform.security.authentication import get_current_identity_id
from camp_match.shared_kernel.application.pagination import PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/bookings", tags=["Bookings"])


def _build_booking_response(booking) -> schemas.BookingResponseSchema:
    return schemas.BookingResponseSchema.model_validate({
        "id": booking.id.value,
        "student_id": booking.student_id.value,
        "listing_id": booking.listing_id.value,
        "unit_id": booking.unit_id.value,
        "property_id": booking.property_id.value,
        "status": booking.status.value,
        "price": {
            "amount_kobo": booking.price.amount_kobo,
            "currency": booking.price.currency.value,
            "period": booking.price.period.value,
        },
        "verification_confirmed_at_booking": booking.verification_confirmed_at_booking,
        "idempotency_key": booking.idempotency_key,
        "expires_at": booking.expires_at,
        "created_at": booking.created_at,
        "confirmed_at": booking.confirmed_at,
        "cancelled_at": booking.cancelled_at,
        "cancelled_by": booking.cancelled_by.value if booking.cancelled_by else None,
        "cancellation_reason": booking.cancellation_reason,
        "handover_offered_at": booking.handover_offered_at,
        "handover_offered_by": booking.handover_offered_by.value if booking.handover_offered_by else None,
        "handover_accepted_at": booking.handover_accepted_at,
    })


@router.post("", response_model=schemas.BookingResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_booking(
    request: schemas.CreateBookingSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[CreateBookingUseCase, Depends(dependencies.get_create_booking_use_case)],
) -> schemas.BookingResponseSchema:
    booking = await use_case.execute(
        CreateBookingRequest(
            student_id=identity_id,
            listing_id=EntityId(request.listing_id),
            idempotency_key=request.idempotency_key,
        )
    )
    return _build_booking_response(booking)


@router.get("/mine", response_model=schemas.PageSchema[schemas.BookingResponseSchema])
async def list_my_bookings(
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[ListMyBookingsUseCase, Depends(dependencies.get_list_my_bookings_use_case)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> schemas.PageSchema[schemas.BookingResponseSchema]:
    page_result = await use_case.execute(
        ListMyBookingsRequest(
            caller_id=identity_id,
            page=PageRequest(page=page, page_size=page_size),
        )
    )
    items = [_build_booking_response(b) for b in page_result.items]
    return schemas.PageSchema(
        items=items,
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
    )


@router.get("/for-property/{property_id}", response_model=schemas.PageSchema[schemas.BookingResponseSchema])
async def list_bookings_for_property(
    property_id: UUID,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[ListBookingsForPropertyUseCase, Depends(dependencies.get_list_bookings_for_property_use_case)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> schemas.PageSchema[schemas.BookingResponseSchema]:
    page_result = await use_case.execute(
        ListBookingsForPropertyRequest(
            property_id=EntityId(property_id),
            caller_id=identity_id,
            page=PageRequest(page=page, page_size=page_size),
        )
    )
    items = [_build_booking_response(b) for b in page_result.items]
    return schemas.PageSchema(
        items=items,
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
    )


@router.get("/{booking_id}", response_model=schemas.BookingResponseSchema)
async def get_booking(
    booking_id: UUID,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[GetBookingUseCase, Depends(dependencies.get_get_booking_use_case)],
) -> schemas.BookingResponseSchema:
    booking = await use_case.execute(
        GetBookingRequest(
            booking_id=EntityId(booking_id),
            caller_id=identity_id,
        )
    )
    return _build_booking_response(booking)


@router.post("/{booking_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_booking(
    booking_id: UUID,
    request: schemas.CancelBookingSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[CancelBookingUseCase, Depends(dependencies.get_cancel_booking_use_case)],
) -> None:
    await use_case.execute(
        CancelBookingRequest(
            booking_id=EntityId(booking_id),
            caller_id=identity_id,
            cancellation_reason=request.cancellation_reason,
        )
    )


@router.post("/{booking_id}/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_booking(
    booking_id: UUID,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[ConfirmBookingUseCase, Depends(dependencies.get_confirm_booking_use_case)],
) -> None:
    await use_case.execute(
        ConfirmBookingRequest(
            booking_id=EntityId(booking_id),
            caller_id=identity_id,
        )
    )


@router.post("/{booking_id}/handover/offered", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_handover_offered(
    booking_id: UUID,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[ConfirmHandoverOfferedUseCase, Depends(dependencies.get_confirm_handover_offered_use_case)],
) -> None:
    await use_case.execute(
        ConfirmHandoverOfferedRequest(
            booking_id=EntityId(booking_id),
            caller_id=identity_id,
        )
    )


@router.post("/{booking_id}/handover/accepted", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_handover_accepted(
    booking_id: UUID,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[ConfirmHandoverAcceptedUseCase, Depends(dependencies.get_confirm_handover_accepted_use_case)],
) -> None:
    await use_case.execute(
        ConfirmHandoverAcceptedRequest(
            booking_id=EntityId(booking_id),
            caller_id=identity_id,
        )
    )
