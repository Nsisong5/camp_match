from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from camp_match.modules.payment.domain.value_objects import (
    Money,
    OperationStatus,
    PaymentAttemptStatus,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    supports_initiation: bool
    supports_verification: bool
    supports_webhooks: bool
    supports_refunds: bool
    supports_payouts: bool


@dataclass(frozen=True, slots=True)
class InitiatePaymentCommand:
    payment_attempt_id: EntityId
    amount: Money
    idempotency_key: str
    return_context: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PaymentSessionResult:
    provider_reference: str
    checkout_reference: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class VerifiedProviderTransaction:
    provider_reference: str
    amount: Money
    normalized_status: PaymentAttemptStatus
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class NormalizedProviderEvent:
    provider_event_id: str
    event_type: str
    provider_reference: str
    normalized_status: PaymentAttemptStatus
    amount: Money
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderRefundResult:
    provider_operation_reference: str
    normalized_status: OperationStatus
    amount: Money
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderPayoutResult:
    provider_operation_reference: str
    normalized_status: OperationStatus
    amount: Money
    failure_reason: str | None = None


class PaymentInitiationCapability(Protocol):
    async def initiate(self, command: InitiatePaymentCommand) -> PaymentSessionResult:
        ...


class PaymentVerificationCapability(Protocol):
    async def verify_transaction(self, provider_reference: str) -> VerifiedProviderTransaction:
        ...


class WebhookCapability(Protocol):
    async def verify_signature(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        ...

    async def parse_event(self, raw_body: bytes) -> NormalizedProviderEvent:
        ...


class RefundCapability(Protocol):
    async def request_refund(
        self, provider_reference: str, amount: Money, idempotency_key: str
    ) -> ProviderRefundResult:
        ...

    async def get_refund_status(
        self, provider_operation_reference: str
    ) -> ProviderRefundResult:
        ...


class PayoutCapability(Protocol):
    async def initiate_payout(
        self, recipient_reference: str, amount: Money, idempotency_key: str
    ) -> ProviderPayoutResult:
        ...

    async def get_payout_status(
        self, provider_operation_reference: str
    ) -> ProviderPayoutResult:
        ...
