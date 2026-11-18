"""Sync booking facts for review use case."""
from __future__ import annotations

from typing import Any
import structlog

from camp_match.modules.payment.application.ports.outbound import (
    BookingProvider,
    DisputeRepository,
    FundDispositionRepository,
    PaymentRepository,
    ReleaseScheduleRepository,
    TransactionReviewRepository,
)
from camp_match.modules.payment.application.use_cases.open_release_schedule import (
    OpenReleaseScheduleUseCase,
)
from camp_match.modules.payment.domain.release_policy import compute_student_confirmed_at
from camp_match.modules.payment.domain.review_stage import derive_review_stage_and_action
from camp_match.modules.payment.domain.value_objects import DisputeStatus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class SyncBookingFactsForReviewUseCase:
    def __init__(
        self,
        payment_repo: PaymentRepository,
        fund_disposition_repo: FundDispositionRepository,
        dispute_repo: DisputeRepository,
        schedule_repo: ReleaseScheduleRepository,
        review_repo: TransactionReviewRepository,
        booking_provider: BookingProvider,
        open_schedule_uc: OpenReleaseScheduleUseCase,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.payment_repo = payment_repo
        self.fund_disposition_repo = fund_disposition_repo
        self.dispute_repo = dispute_repo
        self.schedule_repo = schedule_repo
        self.review_repo = review_repo
        self.booking_provider = booking_provider
        self.open_schedule_uc = open_schedule_uc
        self.uow = uow
        self.clock = clock

    async def execute(self, booking_id: EntityId) -> None:
        reviews = await self.review_repo.get_by_booking_id(booking_id)
        if not reviews:
            return

        booking = await self.booking_provider.get_booking(booking_id)
        if not booking:
            return

        student_confirmed_at = compute_student_confirmed_at(
            booking.handover_offered_at, booking.handover_accepted_at
        )

        for review in reviews:
            payment_id = EntityId(review.payment_id) if hasattr(review, "payment_id") else review["payment_id"]
            if isinstance(payment_id, str):
                payment_id = EntityId.from_string(payment_id)

            fd = await self.fund_disposition_repo.get_by_payment_id(payment_id)
            dispute = await self.dispute_repo.get_open_by_fund_disposition_id(fd.id) if fd else None
            dispute_status = DisputeStatus(dispute.status) if dispute else None

            # Operations for disposition
            operations = [] # operations can be fetched if needed, or derived from review sums

            stage, next_action = derive_review_stage_and_action(
                fund_disposition=fd,
                operations=operations,
                dispute_status=dispute_status,
                booking_status=booking.status,
                handover_status=booking,
                student_confirmed_at=student_confirmed_at,
            )

            async with self.uow:
                await self.review_repo.update_conditional(
                    payment_id,
                    review.version,
                    {
                        "booking_status": booking.status,
                        "handover_offered_at": booking.handover_offered_at,
                        "handover_accepted_at": booking.handover_accepted_at,
                        "student_confirmed_at": student_confirmed_at,
                        "stage": stage.value,
                        "next_action": next_action.value,
                    },
                )
                await self.uow.commit()

            # If student confirmed and schedule not opened yet, open schedule
            if student_confirmed_at is not None and fd:
                schedule = await self.schedule_repo.get_by_fund_disposition_id(fd.id)
                if not schedule:
                    await self.open_schedule_uc.execute(payment_id)
