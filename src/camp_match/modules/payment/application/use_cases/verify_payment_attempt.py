from __future__ import annotations

import structlog

from camp_match.modules.payment.application.ports.outbound import (
    BookingConfirmationPort,
    FundDispositionRepository,
    PaymentAttemptRepository,
    PaymentRepository,
)
from camp_match.modules.payment.application.ports.provider import (
    PaymentVerificationCapability,
)
from camp_match.modules.payment.domain.entities import FundDisposition, Payment
from camp_match.modules.payment.domain.value_objects import (
    FundDispositionStatus,
    PaymentAttemptStatus,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class VerifyPaymentAttemptUseCase:
    def __init__(
        self,
        attempt_repo: PaymentAttemptRepository,
        payment_repo: PaymentRepository,
        fund_disposition_repo: FundDispositionRepository,
        verification_provider: PaymentVerificationCapability,
        booking_confirmation_port: BookingConfirmationPort,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.attempt_repo = attempt_repo
        self.payment_repo = payment_repo
        self.fund_disposition_repo = fund_disposition_repo
        self.verification_provider = verification_provider
        self.booking_confirmation_port = booking_confirmation_port
        self.uow = uow
        self.clock = clock

    async def execute(self, attempt_id: EntityId, provider_reference: str) -> bool:
        verified_tx = await self.verification_provider.verify_transaction(provider_reference)
        now = self.clock.now()

        attempt = await self.attempt_repo.get_by_id(attempt_id)
        if not attempt:
            logger.warning("verify_attempt_not_found", attempt_id=attempt_id)
            return False

        if verified_tx.amount.amount_kobo != attempt.amount.amount_kobo or verified_tx.amount.currency != attempt.amount.currency:
            logger.error(
                "verify_attempt_amount_mismatch",
                attempt_id=attempt_id,
                expected=attempt.amount,
                received=verified_tx.amount,
            )
            return False

        if verified_tx.normalized_status != PaymentAttemptStatus.SUCCEEDED:
            logger.info("verify_attempt_not_succeeded", attempt_id=attempt_id, status=verified_tx.normalized_status)
            return False

        async with self.uow:
            current = await self.attempt_repo.get_by_id(attempt_id)
            if not current:
                return False
            if current.status == PaymentAttemptStatus.SUCCEEDED:
                existing_payment = await self.payment_repo.get_by_payment_attempt_id(attempt_id)
                return existing_payment is not None

            if current.status != PaymentAttemptStatus.PENDING:
                logger.warning("verify_attempt_invalid_state", attempt_id=attempt_id, status=current.status)
                return False

            updated = await self.attempt_repo.update_status(
                attempt_id,
                PaymentAttemptStatus.SUCCEEDED,
                provider_reference=provider_reference,
                confirmed_at=now,
            )
            if not updated:
                return False

            payment_id = EntityId.new()
            payment = Payment(
                id=payment_id,
                payment_attempt_id=attempt_id,
                booking_id=attempt.booking_id,
                student_id=attempt.student_id,
                amount=attempt.amount,
                provider_reference=provider_reference,
                confirmed_at=now,
            )
            await self.payment_repo.add(payment)

            fund_disposition = FundDisposition(
                id=EntityId.new(),
                payment_id=payment_id,
                held_amount_kobo=attempt.amount.amount_kobo,
                status=FundDispositionStatus.HELD,
                created_at=now,
            )
            await self.fund_disposition_repo.add(fund_disposition)
            await self.uow.commit()

        booking_confirmed = await self.booking_confirmation_port.confirm_booking(
            attempt.booking_id, attempt.student_id
        )

        if not booking_confirmed:
            logger.warning(
                "booking_confirmation_rejected_late_payment",
                booking_id=attempt.booking_id,
                attempt_id=attempt_id,
            )
            async with self.uow:
                await self.fund_disposition_repo.update_status(
                    fund_disposition.id, FundDispositionStatus.RECONCILIATION_REQUIRED
                )
                await self.uow.commit()

        logger.info("verify_payment_attempt_success", attempt_id=attempt_id, booking_confirmed=booking_confirmed)
        return True
