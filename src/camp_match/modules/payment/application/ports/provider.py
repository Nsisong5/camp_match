from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from camp_match.modules.payment.domain.provider_contracts import (
    Bank,
    ProviderStatusDetail,
    ResolvedAccount,
    SubjectKind,
)
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
    supports_bank_directory: bool
    supports_payout_recipients: bool
    supports_refund_recovery: bool
    supports_balance: bool


@dataclass(frozen=True, slots=True)
class InitiatePaymentCommand:
    payment_attempt_id: EntityId
    amount: Money
    idempotency_key: str
    payer_email: str
    return_context: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PaymentSessionResult:
    provider_reference: str
    checkout_reference: str
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class VerifiedProviderTransaction:
    provider_reference: str
    amount: Money
    normalized_status: PaymentAttemptStatus
    occurred_at: datetime
    fee_kobo: int | None = None


@dataclass(frozen=True, slots=True)
class NormalizedProviderEvent:
    provider_event_id: str
    event_type: str
    provider_reference: str
    normalized_status: PaymentAttemptStatus
    amount: Money
    occurred_at: datetime
    subject_kind: SubjectKind
    operation_status: OperationStatus | None = None
    provider_operation_reference: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderRefundResult:
    provider_operation_reference: str
    normalized_status: OperationStatus
    amount: Money
    failure_reason: str | None = None
    fee_kobo: int | None = None
    provider_operation_id: str | None = None
    provider_status_detail: ProviderStatusDetail | None = None


@dataclass(frozen=True, slots=True)
class ProviderPayoutResult:
    provider_operation_reference: str
    normalized_status: OperationStatus
    amount: Money
    failure_reason: str | None = None
    fee_kobo: int | None = None
    provider_operation_id: str | None = None


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


class BankDirectoryCapability(Protocol):
    async def list_banks(self) -> list[Bank]:
        ...

    async def resolve_account(self, bank_code: str, account_number: str) -> ResolvedAccount:
        ...


class PayoutRecipientCapability(Protocol):
    async def create_recipient(
        self, account_name: str, bank_code: str, account_number: str
    ) -> str:
        ...


class RefundRecoveryCapability(Protocol):
    async def retry_refund_with_account(
        self, provider_operation_id: str, bank_code: str, account_number: str
    ) -> ProviderRefundResult:
        ...


class ProviderBalanceCapability(Protocol):
    async def get_available_balance(self) -> Money:
        ...
