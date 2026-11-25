from __future__ import annotations

from typing import Any

from pydantic import BaseModel

class PaystackResponse(BaseModel):
    status: bool
    message: str
    data: dict[str, Any] | None = None

class InitiateResponseData(BaseModel):
    authorization_url: str
    access_code: str
    reference: str

class InitiatePaymentResponse(PaystackResponse):
    data: InitiateResponseData  # type: ignore[assignment]

class VerifyResponseData(BaseModel):
    status: str
    reference: str
    amount: int
    currency: str
    gateway_response: str
    fees: int | None = None
    paid_at: str | None = None

class VerifyPaymentResponse(PaystackResponse):
    data: VerifyResponseData  # type: ignore[assignment]
