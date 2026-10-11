from __future__ import annotations

from datetime import datetime
from typing import Generic, List, TypeVar
from uuid import UUID
from pydantic import BaseModel


class CreateBookingSchema(BaseModel):
    listing_id: UUID
    idempotency_key: str


class CancelBookingSchema(BaseModel):
    cancellation_reason: str


class PriceSnapshotSchema(BaseModel):
    amount_kobo: int
    currency: str
    period: str


class BookingResponseSchema(BaseModel):
    id: UUID
    student_id: UUID
    listing_id: UUID
    unit_id: UUID
    property_id: UUID
    status: str
    price: PriceSnapshotSchema
    verification_confirmed_at_booking: bool
    idempotency_key: str
    expires_at: datetime
    created_at: datetime
    confirmed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancelled_by: UUID | None = None
    cancellation_reason: str | None = None


T = TypeVar("T")

class PageSchema(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
