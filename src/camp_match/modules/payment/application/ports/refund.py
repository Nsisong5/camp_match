from __future__ import annotations

from typing import Protocol

from camp_match.modules.payment.domain.value_objects import Money
from camp_match.modules.payment.application.ports.provider import ProviderRefundResult


class RefundCapability(Protocol):
    async def request_refund(
        self, provider_reference: str, amount: Money, idempotency_key: str
    ) -> ProviderRefundResult:
        ...

    async def get_refund_status(
        self, provider_operation_reference: str
    ) -> ProviderRefundResult:
        ...

    async def retry_refund_with_account(
        self, provider_operation_id: str, bank_code: str, account_number: str
    ) -> ProviderRefundResult:
        ...
