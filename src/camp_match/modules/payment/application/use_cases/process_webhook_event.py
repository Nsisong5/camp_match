from __future__ import annotations

import hashlib
import uuid

import structlog

from camp_match.modules.payment.application.ports.outbound import (
    BookingProvider,
    PaymentAttemptRepository,
    WebhookEventRepository,
)
from camp_match.modules.payment.application.ports.provider import WebhookCapability
from camp_match.modules.payment.application.use_cases.verify_payment_attempt import (
    VerifyPaymentAttemptUseCase,
)
from camp_match.modules.payment.domain.events import PaymentOutcomeRecorded
from camp_match.modules.payment.domain.value_objects import (
    PaymentAttemptStatus,
    WebhookProcessingOutcome,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class ProcessWebhookEventUseCase:
    def __init__(
        self,
        webhook_repo: WebhookEventRepository,
        attempt_repo: PaymentAttemptRepository,
        webhook_capability: WebhookCapability,
        verify_payment_attempt_use_case: VerifyPaymentAttemptUseCase,
        booking_provider: BookingProvider,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.webhook_repo = webhook_repo
        self.attempt_repo = attempt_repo
        self.webhook_capability = webhook_capability
        self.verify_payment_attempt_use_case = verify_payment_attempt_use_case
        self.booking_provider = booking_provider
        self.uow = uow
        self.clock = clock

    async def execute(
        self, provider_name: str, raw_body: bytes, headers: dict[str, str]
    ) -> tuple[WebhookProcessingOutcome, str | None]:
        now = self.clock.now()
        payload_digest = hashlib.sha256(raw_body).hexdigest()

        # 1. Verify signature first
        is_valid_sig = await self.webhook_capability.verify_signature(raw_body, headers)
        if not is_valid_sig:
            logger.warning("webhook_signature_verification_failed", provider_name=provider_name)
            event_id_fallback = f"failed_sig_{now.timestamp()}"
            async with self.uow:
                await self.webhook_repo.add(
                    provider_name=provider_name,
                    provider_event_id=event_id_fallback,
                    raw_payload_digest=payload_digest,
                    normalized_event_type="UNKNOWN",
                    processing_status="FAILED_VALIDATION",
                )
                await self.uow.commit()
            return WebhookProcessingOutcome.REJECTED_INVALID_SIGNATURE, "invalid_signature"

        # 2. Parse event
        event = await self.webhook_capability.parse_event(raw_body)

        # 3. Deduplicate
        existing_event = await self.webhook_repo.get_by_provider_event_id(event.provider_event_id)
        if existing_event:
            logger.info("webhook_event_duplicate_ignored", provider_event_id=event.provider_event_id)
            async with self.uow:
                await self.webhook_repo.add(
                    provider_name=provider_name,
                    provider_event_id=f"dup_{event.provider_event_id}_{now.timestamp()}",
                    raw_payload_digest=payload_digest,
                    normalized_event_type=event.event_type,
                    processing_status="IGNORED_DUPLICATE",
                )
                await self.uow.commit()
            return WebhookProcessingOutcome.IGNORED_DUPLICATE, "duplicate_webhook"

        # 4. Correlate to PaymentAttempt
        attempt = await self.attempt_repo.get_by_provider_reference(event.provider_reference)
        if not attempt:
            logger.warning("webhook_event_uncorrelated", provider_reference=event.provider_reference)
            async with self.uow:
                await self.webhook_repo.add(
                    provider_name=provider_name,
                    provider_event_id=event.provider_event_id,
                    raw_payload_digest=payload_digest,
                    normalized_event_type=event.event_type,
                    processing_status="UNCORRELATED",
                )
                await self.uow.commit()
            return WebhookProcessingOutcome.UNCORRELATED, "uncorrelated"

        # 5. Verify amount and currency match
        if event.amount.amount_kobo != attempt.amount.amount_kobo or event.amount.currency != attempt.amount.currency:
            logger.error(
                "webhook_event_amount_mismatch",
                attempt_id=attempt.id,
                expected=attempt.amount,
                received=event.amount,
            )
            async with self.uow:
                booking = await self.booking_provider.get_booking(attempt.booking_id)
                if booking:
                    event_id_val = EntityId(
                        uuid.uuid5(uuid.NAMESPACE_DNS, f"{attempt.id.value}:NEEDS_REVIEW")
                    )
                    self.uow.add_event(
                        PaymentOutcomeRecorded(
                            event_id=event_id_val,
                            payment_attempt_id=attempt.id,
                            booking_id=attempt.booking_id,
                            student_id=attempt.student_id,
                            property_id=booking.property_id,
                            listing_id=booking.listing_id,
                            outcome="NEEDS_REVIEW",
                        )
                    )
                await self.webhook_repo.add(
                    provider_name=provider_name,
                    provider_event_id=event.provider_event_id,
                    raw_payload_digest=payload_digest,
                    normalized_event_type=event.event_type,
                    processing_status="FAILED_VALIDATION",
                    correlated_attempt_id=attempt.id,
                )
                await self.uow.commit()
            return WebhookProcessingOutcome.REJECTED_AMOUNT_MISMATCH, "amount_mismatch"

        # 6. Branch on attempt's current status
        outcome = WebhookProcessingOutcome.PROCESSED_NO_CHANGE
        reason_code = None

        if attempt.status == PaymentAttemptStatus.PENDING:
            success = await self.verify_payment_attempt_use_case.execute(attempt.id, event.provider_reference)
            if success:
                outcome = WebhookProcessingOutcome.PROCESSED_CONFIRMED
            else:
                outcome = WebhookProcessingOutcome.PROVIDER_REPORTED_FAILURE
                reason_code = "provider_failure"
        elif attempt.status in {PaymentAttemptStatus.SUCCEEDED, PaymentAttemptStatus.FAILED, PaymentAttemptStatus.EXPIRED, PaymentAttemptStatus.CANCELLED}:
            if event.normalized_status == PaymentAttemptStatus.SUCCEEDED:
                try:
                    attempt.record_late_success_signal()
                    async with self.uow:
                        booking = await self.booking_provider.get_booking(attempt.booking_id)
                        if booking:
                            event_id_val = EntityId(
                                uuid.uuid5(uuid.NAMESPACE_DNS, f"{attempt.id.value}:LATE_SUCCESS")
                            )
                            self.uow.add_event(
                                PaymentOutcomeRecorded(
                                    event_id=event_id_val,
                                    payment_attempt_id=attempt.id,
                                    booking_id=attempt.booking_id,
                                    student_id=attempt.student_id,
                                    property_id=booking.property_id,
                                    listing_id=booking.listing_id,
                                    outcome="LATE_SUCCESS",
                                )
                            )
                        await self.uow.commit()
                    outcome = WebhookProcessingOutcome.LATE_SUCCESS_FLAGGED
                    reason_code = "late_success"
                except ValueError:
                    outcome = WebhookProcessingOutcome.PROCESSED_NO_CHANGE

        # 7. Record PROCESSED
        async with self.uow:
            await self.webhook_repo.add(
                provider_name=provider_name,
                provider_event_id=event.provider_event_id,
                raw_payload_digest=payload_digest,
                normalized_event_type=event.event_type,
                processing_status="PROCESSED",
                correlated_attempt_id=attempt.id,
            )
            await self.uow.commit()

        logger.info("webhook_event_processed_successfully", provider_event_id=event.provider_event_id, outcome=outcome)
        return outcome, reason_code
