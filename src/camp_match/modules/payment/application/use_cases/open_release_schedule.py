"""Open release schedule use case."""
from __future__ import annotations

from datetime import datetime
from typing import Any
import structlog

from camp_match.modules.payment.application.ports.outbound import (
    BookingProvider,
    FundDispositionRepository,
    PaymentRepository,
    ReleaseScheduleRepository,
    TransactionReviewRepository,
)
from camp_match.modules.payment.domain.events import PaymentReleaseDue
from camp_match.modules.payment.domain.release_policy import compute_student_confirmed_at
from camp_match.modules.payment.domain.release_schedule import compute_warning_due_dates
from camp_match.modules.payment.domain.value_objects import FundDispositionStatus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class OpenReleaseScheduleUseCase:
    def __init__(
        self,
        payment_repo: PaymentRepository,
        fund_disposition_repo: FundDispositionRepository,
        schedule_repo: ReleaseScheduleRepository,
        review_repo: TransactionReviewRepository,
        booking_provider: BookingProvider,
        uow: UnitOfWork,
        clock: Clock,
        settings_view: Any,
    ) -> None:
        self.payment_repo = payment_repo
        self.fund_disposition_repo = fund_disposition_repo
        self.schedule_repo = schedule_repo
        self.review_repo = review_repo
        self.booking_provider = booking_provider
        self.uow = uow
        self.clock = clock
        self.settings_view = settings_view

    async def execute(self, payment_id: EntityId) -> bool:
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            return False
        fd = await self.fund_disposition_repo.get_by_payment_id(payment_id)
        if not fd or fd.status != FundDispositionStatus.HELD:
            return False

        booking = await self.booking_provider.get_booking(payment.booking_id)
        if not booking or booking.status != "CONFIRMED":
            return False

        student_confirmed_at = compute_student_confirmed_at(
            booking.handover_offered_at, booking.handover_accepted_at
        )
        if student_confirmed_at is None:
            return False

        now = self.clock.now()
        schedule_id = EntityId.new()

        async with self.uow:
            inserted = await self.schedule_repo.add_schedule_if_not_exists(
                schedule_id=schedule_id,
                fund_disposition_id=fd.id,
                payment_id=payment.id,
                booking_id=booking.id,
                student_confirmed_at=student_confirmed_at,
                cycle=1,
                window_starts_at=now,
            )
            if not inserted:
                return False

            delay_hours = getattr(self.settings_view, "payment_auto_release_delay_hours", 48)
            offsets_raw = getattr(self.settings_view, "payment_release_warning_offsets_hours", "24,12,3")
            offsets = [int(x.strip()) for x in offsets_raw.split(",")]
            due_dates = compute_warning_due_dates(now, delay_hours, offsets)

            warnings = []
            for i, due_at in enumerate(due_dates, start=1):
                warnings.append({
                    "id": EntityId.new().value,
                    "release_schedule_id": schedule_id.value,
                    "cycle": 1,
                    "warning_number": i,
                    "due_at": due_at,
                })
            await self.schedule_repo.add_warnings(warnings)

            review = await self.review_repo.get_by_payment_id(payment.id)
            if review:
                await self.review_repo.update_conditional(
                    payment.id,
                    review.version,
                    {
                        "release_cycle": 1,
                        "release_window_starts_at": now,
                        "warnings_required": len(offsets),
                        "warnings_sent": 0,
                    },
                )

            self.uow.add_event(
                PaymentReleaseDue(
                    event_id=EntityId.new(),
                    payment_id=payment.id,
                    booking_id=booking.id,
                    student_id=payment.student_id,
                    cycle=1,
                )
            )
            await self.uow.commit()

        logger.info("release_schedule_opened", payment_id=payment.id, cycle=1)
        return True
