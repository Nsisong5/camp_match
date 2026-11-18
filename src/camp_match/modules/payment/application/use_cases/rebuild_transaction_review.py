"""Rebuild transaction review use case."""
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
from camp_match.modules.payment.domain.release_policy import HandoverStatusSnapshot
from camp_match.modules.payment.domain.review_stage import derive_review_stage_and_action
from camp_match.modules.payment.domain.value_objects import DisputeStatus, ReviewStage, ReviewNextAction
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger(__name__)


class RebuildTransactionReviewUseCase:
    def __init__(
        self,
        payment_repo: PaymentRepository,
        fund_disposition_repo: FundDispositionRepository,
        booking_provider: BookingProvider,
        dispute_repo: DisputeRepository,
        schedule_repo: ReleaseScheduleRepository,
        review_repo: TransactionReviewRepository,
    ) -> None:
        self.payment_repo = payment_repo
        self.fund_disposition_repo = fund_disposition_repo
        self.booking_provider = booking_provider
        self.dispute_repo = dispute_repo
        self.schedule_repo = schedule_repo
        self.review_repo = review_repo

    async def execute(self, payment_id: EntityId) -> Any | None:
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            return None

        fd = await self.fund_disposition_repo.get_by_payment_id(payment_id)
        if not fd:
            return None

        booking = await self.booking_provider.get_booking(payment.booking_id)
        dispute = await self.dispute_repo.get_open_by_fund_disposition_id(fd.id)
        dispute_status = DisputeStatus(dispute.status) if dispute else None
        schedule = await self.schedule_repo.get_by_fund_disposition_id(fd.id)

        handover_offered_at = booking.handover_offered_at if booking else None
        handover_accepted_at = booking.handover_accepted_at if booking else None
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

        review = await self.review_repo.get_by_payment_id(payment_id)
        if review:
            await self.review_repo.update_conditional(
                payment_id=payment_id,
                expected_version=review.version,
                values={
                    "stage": stage.value,
                    "next_action": next_action.value if next_action else None,
                    "student_confirmed_at": student_confirmed_at,
                    "open_dispute_id": dispute.id if dispute else None,
                    "dispute_count": (review.dispute_count or 0) + (1 if dispute else 0),
                },
            )
            return await self.review_repo.get_by_payment_id(payment_id)
        return review
