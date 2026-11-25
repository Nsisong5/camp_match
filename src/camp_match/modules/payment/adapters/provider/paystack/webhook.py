from __future__ import annotations

import hmac
import hashlib
import json
from typing import Any
import structlog
from camp_match.config.settings import Settings
from camp_match.modules.payment.application.ports.provider import NormalizedProviderEvent
from camp_match.modules.payment.domain.provider_contracts import SubjectKind
from camp_match.modules.payment.domain.value_objects import PaymentAttemptStatus, Money, Currency

logger = structlog.get_logger(__name__)

class PaystackWebhookHandler:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def verify_signature(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        signature = headers.get("x-paystack-signature")
        if not signature or not self._settings.paystack_secret_key:
            return False
        
        expected_signature = hmac.new(
            self._settings.paystack_secret_key.get_secret_value().encode(),
            raw_body,
            hashlib.sha512,
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)

    def parse_event(self, raw_body: bytes) -> NormalizedProviderEvent:
        event_data = json.loads(raw_body)
        event_type = event_data.get("event")
        data = event_data.get("data", {})
        
        # Determine subject kind and status
        if event_type == "charge.success":
            subject_kind = SubjectKind.PAYMENT
            status = PaymentAttemptStatus.SUCCEEDED
            provider_ref = data.get("reference", "")
            amount = Money(amount_kobo=data.get("amount", 0))
        elif event_type.startswith("refund."):
            subject_kind = SubjectKind.REFUND
            status = PaymentAttemptStatus.SUCCEEDED # Simplified
            provider_ref = data.get("transaction", {}).get("reference", "")
            amount = Money(amount_kobo=data.get("amount", 0))
        elif event_type.startswith("transfer."):
            subject_kind = SubjectKind.PAYOUT
            status = PaymentAttemptStatus.SUCCEEDED # Simplified
            provider_ref = data.get("reference", "")
            amount = Money(amount_kobo=data.get("amount", 0))
        else:
            subject_kind = SubjectKind.UNSUPPORTED
            status = PaymentAttemptStatus.FAILED
            provider_ref = ""
            amount = Money(amount_kobo=0)
            
        return NormalizedProviderEvent(
            provider_event_id=str(event_data.get("id")),
            event_type=event_type,
            provider_reference=provider_ref,
            normalized_status=status,
            amount=amount,
            occurred_at=datetime.now(UTC),
            subject_kind=subject_kind,
        )
from datetime import datetime, UTC
