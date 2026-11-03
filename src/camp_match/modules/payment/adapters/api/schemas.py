from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel


class CreatePaymentSchema(BaseModel):
    booking_id: UUID
    idempotency_key: str
    provider_name: str = "mock"


class PaymentSessionResponseSchema(BaseModel):
    provider_reference: str
    checkout_reference: str
    expires_at: datetime


class PaymentResponseSchema(BaseModel):
    id: UUID
    payment_attempt_id: UUID
    booking_id: UUID
    student_id: UUID
    amount_kobo: int
    currency: str
    provider_reference: str
    confirmed_at: datetime


class PaymentAttemptResponseSchema(BaseModel):
    id: UUID
    booking_id: UUID
    student_id: UUID
    amount_kobo: int
    currency: str
    status: str
    provider_name: str
    provider_reference: str | None = None
    created_at: datetime
    confirmed_at: datetime | None = None


class CreateDisputeSchema(BaseModel):
    reason: str


class DisputeResponseSchema(BaseModel):
    id: UUID
    fund_disposition_id: UUID
    raised_by: UUID
    reason: str
    status: str
    raised_at: datetime
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None
    resolution_notes: str | None = None


class ResolveDisputeSchema(BaseModel):
    resolution: str  # RELEASE or REFUND
    notes: str


class ReleaseRequestSchema(BaseModel):
    reason: str


class RefundRequestSchema(BaseModel):
    reason: str


T = TypeVar("T")


class PageSchema(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
