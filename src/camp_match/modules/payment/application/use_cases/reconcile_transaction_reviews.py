"""Reconcile transaction reviews use case."""
from __future__ import annotations

import structlog
from typing import Any

from camp_match.modules.payment.application.ports.outbound import (
    BookingProvider,
    DisputeRepository,
    FundDispositionRepository,
    PaymentRepository,
    ReleaseScheduleRepository,
    TransactionReviewRepository,
)
from camp_match.modules.payment.application.use_cases.open_release_schedule import OpenReleaseScheduleUseCase
from camp_match.modules.payment.domain.release_policy import HandoverStatusSnapshot
from camp_match.modules.payment.domain.review_stage import derive_review_stage_and_action
from camp_match.modules.payment.domain.value_objects import DisputeStatus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger(__name__)


class ReconcileTransactionReviewsUseCase:
    def __init__(
        self,
        payment_repo: PaymentRepository,
        fund_disposition_repo: FundDispositionRepository,
        booking_provider: BookingProvider,
        dispute_repo: DisputeRepository,
        schedule_repo: ReleaseScheduleRepository,
        review_repo: TransactionReviewRepository,
        open_schedule_uc: OpenReleaseScheduleUseCase,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.payment_repo = payment_repo
        self.fund_disposition_repo = fund_disposition_repo
        self.booking_provider = booking_provider
        self.dispute_repo = dispute_repo
        self.schedule_repo = schedule_repo
        self.review_repo = review_repo
        self.open_schedule_uc = open_schedule_uc
        self.uow = uow
        self.clock = clock

    async def execute(self) -> dict[str, int]:
        now = self.clock.now()
        backfilled = 0
        repaired = 0
        layer_4_findings = 0
        out_of_order_findings = 0

        payments = await self.payment_repo.list_confirmed() if hasattr(self.payment_repo, "list_confirmed") else []
        for payment in payments:
            fd = await self.fund_disposition_repo.get_by_payment_id(payment.id)
            if not fd:
                continue

            review = await self.review_repo.get_by_payment_id(payment.id)
            booking = await self.booking_provider.get_booking(payment.booking_id)
            dispute = await self.dispute_repo.get_open_by_fund_disposition_id(fd.id)
            dispute_status = DisputeStatus(dispute.status) if dispute else None
            schedule = await self.schedule_repo.get_by_fund_disposition_id(fd.id)

            handover_offered_at = booking.handover_offered_at if booking else None
            handover_accepted_at = booking.handover_accepted_at if booking else None

            if handover_offered_at and handover_accepted_at and handover_accepted_at < handover_offered_at:
                out_of_order_findings += 1
                logger.warning("out_of_order_booking_facts", booking_id=booking.id)

            student_confirmed_at = schedule.student_confirmed_at if schedule else (
                handover_accepted_at if (handover_offered_at and handover_accepted_at and handover_accepted_at >= handover_offered_at) else None
            )

            handover_status = HandoverStatusSnapshot(offered_at=handover_offered_at, accepted_at=handover_accepted_at)
            operations = fd.release_operations + fd.refund_operations

            stage, next_action = derive_review_stage_and_action(
                fund_disposition=fd,
                operations=operations,
                dispute_status=dispute_status,
                booking_status=booking.status if booking else "CONFIRMED",
                handover_status=handover_status,
                student_confirmed_at=student_confirmed_at,
            )

            if not review:
                # Backfill review row
                from camp_match.modules.payment.adapters.persistence.models import TransactionReviewModel
                review_model = TransactionReviewModel(
                    id=EntityId.new().value,
                    payment_id=payment.id.value,
                    fund_disposition_id=fd.id.value,
                    payment_attempt_id=payment.payment_attempt_id.value if hasattr(payment, "payment_attempt_id") and payment.payment_attempt_id else payment.id.value,
                    booking_id=payment.booking_id.value,
                    student_id=payment.student_id.value if hasattr(payment, "student_id") else payment.booking_id.value,
                    amount_kobo=payment.amount.amount_kobo,
                    currency=payment.amount.currency.value,
                    provider_name="paystack",
                    provider_reference=payment.provider_reference,
                    paid_at=payment.confirmed_at or now,
                    booking_status=booking.status if booking else "CONFIRMED",
                    handover_offered_at=handover_offered_at,
                    handover_accepted_at=handover_accepted_at,
                    student_confirmed_at=student_confirmed_at,
                    stage=stage.value,
                    next_action=next_action.value if next_action else None,
                    next_action_since=now,
                    version=1,
                )
                async with self.uow:
                    await self.review_repo.add(review_model)
                    await self.uow.commit()
                backfilled += 1

                # Open schedule if confirmed and not opened
                if student_confirmed_at and not schedule:
                    try:
                        await self.open_schedule_uc.execute(payment.id)
                    except Exception:
                        pass
            else:
                # Check for repair
                if review.stage != stage.value or review.next_action != (next_action.value if next_action else None):
                    async with self.uow:
                        await self.review_repo.update_conditional(
                            payment_id=payment.id,
                            expected_version=review.version,
                            values={
                                "stage": stage.value,
                                "next_action": next_action.value if next_action else None,
                            },
                        )
                        await self.uow.commit()
                    repaired += 1

        logger.info(
            "reconcile_transaction_reviews_completed",
            backfilled=backfilled,
            repaired=repaired,
            layer_4_findings=layer_4_findings,
            out_of_order_findings=out_of_order_findings,
        )
        return {
            "backfilled": backfilled,
            "repaired": repaired,
            "layer_4_findings": layer_4_findings,
            "out_of_order_findings": out_of_order_findings,
        }
