from __future__ import annotations

import structlog

from camp_match.modules.payment.application.errors import (
    BookingNotEligibleForPayment,
    BookingNotFound,
    PaymentInitiationError,
    UnsupportedProviderCapability,
)
from camp_match.modules.payment.application.ports.inbound import InitiatePaymentRequest
from camp_match.modules.payment.application.ports.outbound import (
    BookingProvider,
    PaymentAttemptRepository,
)
from camp_match.modules.payment.application.ports.provider import (
    InitiatePaymentCommand,
    PaymentInitiationCapability,
    PaymentSessionResult,
)
from camp_match.modules.payment.domain.entities import PaymentAttempt
from camp_match.modules.payment.domain.value_objects import (
    Currency,
    Money,
    PaymentAttemptStatus,
)
from camp_match.shared_kernel.application.errors import ForbiddenError
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class InitiatePaymentUseCase:
    def __init__(
        self,
        attempt_repo: PaymentAttemptRepository,
        booking_provider: BookingProvider,
        payment_initiation_provider: PaymentInitiationCapability,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.attempt_repo = attempt_repo
        self.booking_provider = booking_provider
        self.payment_initiation_provider = payment_initiation_provider
        self.uow = uow
        self.clock = clock

    async def execute(self, request: InitiatePaymentRequest) -> PaymentSessionResult:
        existing = await self.attempt_repo.get_by_idempotency_key(request.caller_id, request.idempotency_key)
        if existing:
            logger.info(
                "payment_attempt_idempotent_replay",
                student_id=request.caller_id,
                idempotency_key=request.idempotency_key,
                attempt_id=existing.id,
            )
            return PaymentSessionResult(
                provider_reference=existing.provider_reference or "",
                checkout_reference=f"https://mockpay.test/checkout/{existing.provider_reference}" if existing.provider_reference else "",
                expires_at=self.clock.now(),
            )

        booking = await self.booking_provider.get_booking(request.booking_id)
        if not booking:
            raise BookingNotFound("Booking not found.")

        if request.caller_id != booking.student_id:
            raise ForbiddenError("Only the booking student can initiate payment.")

        now = self.clock.now()
        if booking.status != "AWAITING_PAYMENT" or booking.expires_at < now:
            raise BookingNotEligibleForPayment("Booking is not awaiting payment or hold has expired.")

        amount = Money(amount_kobo=booking.amount_kobo, currency=Currency(booking.currency))

        attempt_id = EntityId.new()
        attempt = PaymentAttempt(
            id=attempt_id,
            booking_id=request.booking_id,
            student_id=request.caller_id,
            amount=amount,
            idempotency_key=request.idempotency_key,
            status=PaymentAttemptStatus.INITIATED,
            provider_name=request.provider_name,
            created_at=now,
        )

        async with self.uow:
            await self.attempt_repo.add(attempt)
            await self.uow.commit()

        if hasattr(self.payment_initiation_provider, "capabilities"):
            caps = self.payment_initiation_provider.capabilities
            if not caps.supports_initiation:
                raise UnsupportedProviderCapability("Provider does not support initiation.")

        command = InitiatePaymentCommand(
            payment_attempt_id=attempt_id,
            amount=amount,
            idempotency_key=request.idempotency_key,
            return_context=request.return_context,
        )

        try:
            session_result = await self.payment_initiation_provider.initiate(command)
        except Exception as e:
            async with self.uow:
                await self.attempt_repo.update_status(
                    attempt_id,
                    PaymentAttemptStatus.FAILED,
                    provider_reference=None,
                )
                await self.uow.commit()
            logger.warning(
                "payment_initiation_failed",
                attempt_id=attempt_id,
                error=str(e),
            )
            raise PaymentInitiationError(f"Payment initiation failed: {e}") from e

        async with self.uow:
            await self.attempt_repo.update_status(
                attempt_id,
                PaymentAttemptStatus.PENDING,
                provider_reference=session_result.provider_reference,
            )
            await self.uow.commit()

        logger.info(
            "payment_initiation_succeeded",
            attempt_id=attempt_id,
            provider_reference=session_result.provider_reference,
        )

        return session_result
