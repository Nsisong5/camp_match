from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from camp_match.modules.payment.application.ports.provider import PaymentSessionResult
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, slots=True)
class InitiatePaymentRequest:
    booking_id: EntityId
    caller_id: EntityId
    idempotency_key: str
    provider_name: str = "mock"
    return_context: dict[str, str] = field(default_factory=dict)


class InitiatePayment(Protocol):
    async def execute(self, request: InitiatePaymentRequest) -> PaymentSessionResult:
        ...
