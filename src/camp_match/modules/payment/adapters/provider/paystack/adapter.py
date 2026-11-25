from __future__ import annotations

from typing import Any

from camp_match.config.settings import Settings
from camp_match.modules.payment.adapters.provider.paystack.client import PaystackClient
from camp_match.modules.payment.adapters.provider.paystack.webhook import PaystackWebhookHandler
from camp_match.modules.payment.adapters.provider.paystack.schemas import (
    InitiatePaymentResponse,
    VerifyPaymentResponse,
)
from camp_match.modules.payment.application.ports.provider import (
    InitiatePaymentCommand,
    PaymentSessionResult,
    ProviderCapabilities,
    VerifiedProviderTransaction,
    NormalizedProviderEvent,
    ProviderRefundResult,
)
from camp_match.modules.payment.domain.value_objects import PaymentAttemptStatus, Money, OperationStatus
from datetime import datetime, UTC


class PaystackPaymentProviderAdapter:
    def __init__(self, client: PaystackClient, webhook_handler: PaystackWebhookHandler) -> None:
        self._client = client
        self._webhook_handler = webhook_handler
        self.capabilities = ProviderCapabilities(
            supports_initiation=True,
            supports_verification=True,
            supports_webhooks=True,
            supports_refunds=True,
            supports_payouts=False,
            supports_bank_directory=False,
            supports_payout_recipients=True,
            supports_refund_recovery=True,
            supports_balance=False,
        )

    async def initiate(self, command: InitiatePaymentCommand) -> PaymentSessionResult:
        payload = {
            "email": command.payer_email,
            "amount": command.amount.amount_kobo,
            "currency": command.amount.currency.value,
            "reference": f"cm-{command.payment_attempt_id.value}",
            "callback_url": "https://campmatch.com/callback", # Should come from settings
            "metadata": {"payment_attempt_id": str(command.payment_attempt_id.value)},
        }
        
        response_data = await self._client.post("/transaction/initialize", json=payload)
        response = InitiatePaymentResponse(**response_data)
        
        return PaymentSessionResult(
            provider_reference=response.data.reference,
            checkout_reference=response.data.authorization_url,
            expires_at=None,
        )

    async def verify_transaction(self, provider_reference: str) -> VerifiedProviderTransaction:
        response_data = await self._client.get(f"/transaction/verify/{provider_reference}")
        response = VerifyPaymentResponse(**response_data)
        
        status = PaymentAttemptStatus.SUCCEEDED if response.data.status == "success" else PaymentAttemptStatus.FAILED
        
        return VerifiedProviderTransaction(
            provider_reference=response.data.reference,
            amount=Money(amount_kobo=response.data.amount),
            normalized_status=status,
            occurred_at=datetime.now(UTC),
            fee_kobo=response.data.fees
        )

    async def request_refund(
        self, provider_reference: str, amount: Money, idempotency_key: str
    ) -> ProviderRefundResult:
        payload = {
            "transaction": provider_reference,
            "amount": amount.amount_kobo,
        }
        response_data = await self._client.post("/refund", json=payload)
        # Assuming similar response structure for refunds
        return ProviderRefundResult(
            provider_operation_reference=response_data["data"]["reference"],
            normalized_status=OperationStatus.PROVIDER_PENDING,
            amount=amount,
        )

    async def get_refund_status(
        self, provider_operation_reference: str
    ) -> ProviderRefundResult:
        # Simplification: lookup by reference
        response_data = await self._client.get(f"/refund/{provider_operation_reference}")
        # Map fields accordingly
        return ProviderRefundResult(
            provider_operation_reference=provider_operation_reference,
            normalized_status=OperationStatus.SUCCEEDED, # Simplified
            amount=Money(amount_kobo=0), # Simplified
        )

    async def retry_refund_with_account(
        self, provider_operation_id: str, bank_code: str, account_number: str
    ) -> ProviderRefundResult:
        # Implementation for retry
        return ProviderRefundResult(
            provider_operation_reference="retry-ref",
            normalized_status=OperationStatus.PROVIDER_PENDING,
            amount=Money(amount_kobo=0),
        )

    async def create_recipient(
        self, account_name: str, bank_code: str, account_number: str
    ) -> str:
        payload = {
            "type": "nuban",
            "name": account_name,
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": "NGN",
        }
        response_data = await self._client.post("/transferrecipient", json=payload)
        return str(response_data["data"]["recipient_code"])

    async def verify_signature(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        return self._webhook_handler.verify_signature(raw_body, headers)

    async def parse_event(self, raw_body: bytes) -> NormalizedProviderEvent:
        return self._webhook_handler.parse_event(raw_body)
