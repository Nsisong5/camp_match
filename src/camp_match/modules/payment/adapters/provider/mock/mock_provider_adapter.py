from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from camp_match.modules.payment.application.ports.provider import (
    InitiatePaymentCommand,
    NormalizedProviderEvent,
    PaymentSessionResult,
    ProviderCapabilities,
    ProviderPayoutResult,
    ProviderRefundResult,
    VerifiedProviderTransaction,
)
from camp_match.modules.payment.domain.value_objects import (
    Money,
    OperationStatus,
    PaymentAttemptStatus,
)


class MockPaymentProviderAdapter:
    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities(
            supports_initiation=True,
            supports_verification=True,
            supports_webhooks=True,
            supports_refunds=True,
            supports_payouts=True,
        )
        self._scenarios: dict[str, str] = {}
        self._transactions: dict[str, VerifiedProviderTransaction] = {}
        self._verify_counts: dict[str, int] = {}

    def set_scenario(self, payment_attempt_id: str, scenario: str) -> None:
        self._scenarios[payment_attempt_id] = scenario

    async def initiate(self, command: InitiatePaymentCommand) -> PaymentSessionResult:
        scenario = command.return_context.get("scenario", "success")
        self._scenarios[str(command.payment_attempt_id)] = scenario

        provider_ref = f"mock_prov_ref_{command.payment_attempt_id.value}"
        checkout_ref = f"https://mockpay.test/checkout/{provider_ref}"
        expires_at = datetime.now(UTC) + timedelta(minutes=30)

        initial_status = PaymentAttemptStatus.PENDING if "pending" in scenario else PaymentAttemptStatus.INITIATED
        if scenario == "success":
            initial_status = PaymentAttemptStatus.SUCCEEDED
        elif scenario == "failure":
            initial_status = PaymentAttemptStatus.FAILED
        elif scenario == "timeout":
            initial_status = PaymentAttemptStatus.EXPIRED

        self._transactions[provider_ref] = VerifiedProviderTransaction(
            provider_reference=provider_ref,
            amount=command.amount,
            normalized_status=initial_status,
            occurred_at=datetime.now(UTC),
        )

        return PaymentSessionResult(
            provider_reference=provider_ref,
            checkout_reference=checkout_ref,
            expires_at=expires_at,
        )

    async def verify_transaction(self, provider_reference: str) -> VerifiedProviderTransaction:
        if provider_reference not in self._transactions:
            raise ValueError(f"Unknown provider reference: {provider_reference}")
        tx = self._transactions[provider_reference]
        count = self._verify_counts.get(provider_reference, 0)
        self._verify_counts[provider_reference] = count + 1

        for attempt_id, scenario in self._scenarios.items():
            if provider_reference.endswith(attempt_id):
                if scenario == "pending_then_success":
                    if count == 0:
                        return VerifiedProviderTransaction(
                            provider_reference=tx.provider_reference,
                            amount=tx.amount,
                            normalized_status=PaymentAttemptStatus.PENDING,
                            occurred_at=datetime.now(UTC),
                        )
                    else:
                        return VerifiedProviderTransaction(
                            provider_reference=tx.provider_reference,
                            amount=tx.amount,
                            normalized_status=PaymentAttemptStatus.SUCCEEDED,
                            occurred_at=datetime.now(UTC),
                        )
                elif scenario == "pending_then_failure":
                    if count == 0:
                        return VerifiedProviderTransaction(
                            provider_reference=tx.provider_reference,
                            amount=tx.amount,
                            normalized_status=PaymentAttemptStatus.PENDING,
                            occurred_at=datetime.now(UTC),
                        )
                    else:
                        return VerifiedProviderTransaction(
                            provider_reference=tx.provider_reference,
                            amount=tx.amount,
                            normalized_status=PaymentAttemptStatus.FAILED,
                            occurred_at=datetime.now(UTC),
                        )
        return tx

    async def verify_signature(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        sig = headers.get("x-mock-signature", "")
        if sig == "invalid":
            return False
        return True

    async def parse_event(self, raw_body: bytes) -> NormalizedProviderEvent:
        data = json.loads(raw_body.decode("utf-8"))
        if data.get("invalid_signature"):
            raise ValueError("Invalid signature in mock event")

        status_str = data.get("status", "SUCCEEDED")
        normalized_status = PaymentAttemptStatus(status_str)
        amount_kobo = data.get("amount_kobo", 10000)

        return NormalizedProviderEvent(
            provider_event_id=data.get("event_id", "evt_mock_1"),
            event_type=data.get("event_type", "payment.success"),
            provider_reference=data.get("provider_reference", "mock_prov_ref_default"),
            normalized_status=normalized_status,
            amount=Money(amount_kobo),
            occurred_at=datetime.now(UTC),
        )

    async def request_refund(
        self, provider_reference: str, amount: Money, idempotency_key: str
    ) -> ProviderRefundResult:
        return ProviderRefundResult(
            provider_operation_reference=f"ref_op_{provider_reference}",
            normalized_status=OperationStatus.SUCCEEDED,
            amount=amount,
        )

    async def get_refund_status(
        self, provider_operation_reference: str
    ) -> ProviderRefundResult:
        return ProviderRefundResult(
            provider_operation_reference=provider_operation_reference,
            normalized_status=OperationStatus.SUCCEEDED,
            amount=Money(10000),
        )

    async def initiate_payout(
        self, recipient_reference: str, amount: Money, idempotency_key: str
    ) -> ProviderPayoutResult:
        return ProviderPayoutResult(
            provider_operation_reference=f"payout_op_{recipient_reference}",
            normalized_status=OperationStatus.SUCCEEDED,
            amount=amount,
        )

    async def get_payout_status(
        self, provider_operation_reference: str
    ) -> ProviderPayoutResult:
        return ProviderPayoutResult(
            provider_operation_reference=provider_operation_reference,
            normalized_status=OperationStatus.SUCCEEDED,
            amount=Money(10000),
        )
