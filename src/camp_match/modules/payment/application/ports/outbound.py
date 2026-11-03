from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from camp_match.modules.payment.domain.entities import (
    Dispute,
    FundDisposition,
    Payment,
    PaymentAttempt,
    RefundOperation,
    ReleaseOperation,
)
from camp_match.modules.payment.domain.value_objects import (
    DisputeStatus,
    FundDispositionStatus,
    LedgerEntryType,
    PaymentAttemptStatus,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, slots=True)
class BookingSummary:
    id: EntityId
    status: str
    student_id: EntityId
    property_id: EntityId
    amount_kobo: int
    currency: str
    period: str
    expires_at: datetime
    handover_offered_at: datetime | None = None
    handover_accepted_at: datetime | None = None


class BookingProvider(Protocol):
    async def get_booking(self, booking_id: EntityId) -> BookingSummary | None:
        ...


class BookingConfirmationPort(Protocol):
    async def confirm_booking(self, booking_id: EntityId, caller_id: EntityId) -> bool:
        ...


@dataclass(frozen=True, slots=True)
class WebhookEventRecord:
    id: EntityId
    provider_name: str
    provider_event_id: str
    raw_payload_digest: str
    normalized_event_type: str
    correlated_attempt_id: EntityId | None
    processing_status: str
    received_at: datetime
    processed_at: datetime | None


class WebhookEventRepository(Protocol):
    async def add(
        self,
        provider_name: str,
        provider_event_id: str,
        raw_payload_digest: str,
        normalized_event_type: str,
        processing_status: str,
        correlated_attempt_id: EntityId | None = None,
    ) -> WebhookEventRecord:
        ...

    async def get_by_provider_event_id(self, provider_event_id: str) -> WebhookEventRecord | None:
        ...

    async def update_status(
        self,
        event_id: EntityId,
        status: str,
        processed_at: datetime,
        correlated_attempt_id: EntityId | None = None,
    ) -> bool:
        ...


class PaymentAttemptRepository(Protocol):
    async def add(self, attempt: PaymentAttempt) -> PaymentAttempt:
        ...

    async def get_by_id(self, attempt_id: EntityId) -> PaymentAttempt | None:
        ...

    async def get_by_idempotency_key(
        self, student_id: EntityId, idempotency_key: str
    ) -> PaymentAttempt | None:
        ...

    async def get_by_provider_reference(self, provider_reference: str) -> PaymentAttempt | None:
        ...

    async def update_status(
        self,
        attempt_id: EntityId,
        status: PaymentAttemptStatus,
        provider_reference: str | None = None,
        confirmed_at: datetime | None = None,
    ) -> bool:
        ...


class PaymentRepository(Protocol):
    async def add(self, payment: Payment) -> Payment:
        ...

    async def get_by_id(self, payment_id: EntityId) -> Payment | None:
        ...

    async def get_by_payment_attempt_id(self, payment_attempt_id: EntityId) -> Payment | None:
        ...


class FundDispositionRepository(Protocol):
    async def add(self, disposition: FundDisposition) -> FundDisposition:
        ...

    async def get_by_id(self, disposition_id: EntityId) -> FundDisposition | None:
        ...

    async def get_by_payment_id(self, payment_id: EntityId) -> FundDisposition | None:
        ...

    async def update_status(
        self, disposition_id: EntityId, status: FundDispositionStatus
    ) -> bool:
        ...


class ReleaseOperationRepository(Protocol):
    async def add(self, op: ReleaseOperation) -> ReleaseOperation:
        ...

    async def get_by_id(self, op_id: EntityId) -> ReleaseOperation | None:
        ...


class RefundOperationRepository(Protocol):
    async def add(self, op: RefundOperation) -> RefundOperation:
        ...

    async def get_by_id(self, op_id: EntityId) -> RefundOperation | None:
        ...


class DisputeRepository(Protocol):
    async def add(self, dispute: Dispute) -> Dispute:
        ...

    async def get_by_id(self, dispute_id: EntityId) -> Dispute | None:
        ...

    async def get_open_by_fund_disposition_id(
        self, disposition_id: EntityId
    ) -> Dispute | None:
        ...

    async def update_resolution(
        self,
        dispute_id: EntityId,
        status: DisputeStatus,
        resolved_at: datetime,
        resolved_by: EntityId,
        resolution_notes: str,
    ) -> bool:
        ...


class ReleaseDecisionRepository(Protocol):
    async def add(
        self,
        decision_id: EntityId,
        fund_disposition_id: EntityId,
        decision: str,
        amount_kobo: int,
        currency: str,
        policy_version: str,
        triggering_fact: str,
        origin: str,
        reason: str,
        decided_at: datetime,
        evidence_reference: str | None = None,
        authorized_by: EntityId | None = None,
    ) -> Any:
        ...


class LedgerEntryRepository(Protocol):
    async def add(
        self,
        entry_id: EntityId,
        payment_id: EntityId | None,
        fund_disposition_id: EntityId | None,
        entry_type: LedgerEntryType,
        amount_kobo: int,
        currency: str,
        reference_type: str,
        reference_id: EntityId,
        description: str,
        created_at: datetime,
    ) -> Any:
        ...

    async def get_by_fund_disposition_id(self, disposition_id: EntityId) -> list[Any]:
        ...
