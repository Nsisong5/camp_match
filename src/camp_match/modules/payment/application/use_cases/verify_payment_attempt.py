from __future__ import annotations

import uuid
import structlog

from camp_match.modules.payment.adapters.persistence.models import TransactionReviewModel
from camp_match.modules.payment.application.ports.outbound import (
    BookingConfirmationPort,
    BookingProvider,
    FundDispositionRepository,
    LedgerEntryRepository,
    PaymentAttemptRepository,
    PaymentRepository,
    TransactionReviewRepository,
)
from camp_match.modules.payment.application.ports.provider import (
    PaymentVerificationCapability,
)
from camp_match.modules.payment.domain.entities import FundDisposition, Payment
from camp_match.modules.payment.domain.events import PaymentOutcomeRecorded
from camp_match.modules.payment.domain.release_policy import compute_student_confirmed_at
from camp_match.modules.payment.domain.review_stage import derive_review_stage_and_action
from camp_match.modules.payment.domain.value_objects import (
    FundDispositionStatus,
    LedgerEntryType,
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
        ledger_repo: LedgerEntryRepository,
        verification_provider: PaymentVerificationCapability,
        booking_confirmation_port: BookingConfirmationPort,
        booking_provider: BookingProvider,
        uow: UnitOfWork,
        clock: Clock,
        review_repo: TransactionReviewRepository | None = None,
        housing_provider: Any | None = None,
    ) -> None:
        self.attempt_repo = attempt_repo
        self.payment_repo = payment_repo
        self.fund_disposition_repo = fund_disposition_repo
        self.ledger_repo = ledger_repo
        self.verification_provider = verification_provider
        self.booking_confirmation_port = booking_confirmation_port
        self.booking_provider = booking_provider
        self.uow = uow
        self.clock = clock
        self.review_repo = review_repo
        self.housing_provider = housing_provider

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
            async with self.uow:
                booking = await self.booking_provider.get_booking(attempt.booking_id)
                if booking:
                    event_id_val = EntityId(
                        uuid.uuid5(uuid.NAMESPACE_DNS, f"{attempt.id.value}:FAILED")
                    )
                    self.uow.add_event(
                        PaymentOutcomeRecorded(
                            event_id=event_id_val,
                            payment_attempt_id=attempt.id,
                            booking_id=attempt.booking_id,
                            student_id=attempt.student_id,
                            property_id=booking.property_id,
                            listing_id=booking.listing_id,
                            outcome="FAILED",
                        )
                    )
                await self.uow.commit()
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

            await self.ledger_repo.add(
                entry_id=EntityId.new(),
                payment_id=payment_id,
                fund_disposition_id=fund_disposition.id,
                entry_type=LedgerEntryType.CHARGE,
                amount_kobo=attempt.amount.amount_kobo,
                currency=attempt.amount.currency.value,
                reference_type="PAYMENT",
                reference_id=payment_id,
                description="Payment charge",
                created_at=now,
            )
            await self.ledger_repo.add(
                entry_id=EntityId.new(),
                payment_id=payment_id,
                fund_disposition_id=fund_disposition.id,
                entry_type=LedgerEntryType.HOLD_ALLOCATION,
                amount_kobo=-attempt.amount.amount_kobo,
                currency=attempt.amount.currency.value,
                reference_type="FUND_DISPOSITION",
                reference_id=fund_disposition.id,
                description="Escrow hold allocation",
                created_at=now,
            )

            if self.review_repo is not None:
                prop_id = None
                provider_id = None
                b_status = "AWAITING_PAYMENT"
                h_offered = None
                h_accepted = None
                booking_obj = None
                try:
                    booking_obj = await self.booking_provider.get_booking(attempt.booking_id)
                    if booking_obj:
                        prop_id = booking_obj.property_id
                        b_status = booking_obj.status
                        h_offered = booking_obj.handover_offered_at
                        h_accepted = booking_obj.handover_accepted_at
                        if self.housing_provider is not None and prop_id:
                            try:
                                provider_id = await self.housing_provider.get_property_owner(prop_id)
                            except Exception as ex:
                                logger.warning("verify_payment_provider_lookup_failed", error=str(ex))
                except Exception as ex:
                    logger.warning("verify_payment_booking_lookup_failed", error=str(ex))

                confirmed_at = compute_student_confirmed_at(h_offered, h_accepted)
                stage, next_action = derive_review_stage_and_action(
                    fund_disposition=fund_disposition,
                    operations=[],
                    dispute_status=None,
                    booking_status=b_status,
                    handover_status=booking_obj,
                    student_confirmed_at=confirmed_at,
                )

                review = TransactionReviewModel(
                    id=EntityId.new().value,
                    payment_id=payment_id.value,
                    fund_disposition_id=fund_disposition.id.value,
                    payment_attempt_id=attempt_id.value,
                    booking_id=attempt.booking_id.value,
                    student_id=attempt.student_id.value,
                    provider_id=provider_id.value if provider_id else None,
                    property_id=prop_id.value if prop_id else None,
                    amount_kobo=attempt.amount.amount_kobo,
                    currency=attempt.amount.currency.value,
                    provider_name=attempt.provider_name,
                    provider_reference=provider_reference,
                    paid_at=now,
                    booking_status=b_status,
                    handover_offered_at=h_offered,
                    handover_accepted_at=h_accepted,
                    student_confirmed_at=confirmed_at,
                    stage=stage.value,
                    next_action=next_action.value,
                    next_action_since=now if next_action.value != "NONE" else None,
                )
                await self.review_repo.add(review)

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
                await self.fund_disposition_repo.update_status(
                    fund_disposition.id, FundDispositionStatus.RECONCILIATION_REQUIRED
                )
                await self.uow.commit()

        logger.info("verify_payment_attempt_success", attempt_id=attempt_id, booking_confirmed=booking_confirmed)
        return True
