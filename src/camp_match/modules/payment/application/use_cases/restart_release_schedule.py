"""Restart release schedule use case."""
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
from camp_match.modules.payment.domain.release_schedule import compute_warning_due_dates
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class RestartReleaseScheduleUseCase:
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
        if not fd:
            return False

        schedule = await self.schedule_repo.get_by_fund_disposition_id(fd.id)
        if not schedule:
            return False

        booking = await self.booking_provider.get_booking(payment.booking_id)
        if not booking or booking.status != "CONFIRMED":
            return False

        now = self.clock.now()
        expected_cycle = schedule.cycle

        async with self.uow:
            restarted = await self.schedule_repo.restart_cycle(
                disposition_id=fd.id,
                expected_cycle=expected_cycle,
                new_window_starts_at=now,
            )
            if not restarted:
                return False

            new_cycle = expected_cycle + 1
            delay_hours = getattr(self.settings_view, "payment_auto_release_delay_hours", 48)
            offsets_raw = getattr(self.settings_view, "payment_release_warning_offsets_hours", "24,12,3")
            offsets = [int(x.strip()) for x in offsets_raw.split(",")]
            due_dates = compute_warning_due_dates(now, delay_hours, offsets)

            warnings = []
            for i, due_at in enumerate(due_dates, start=1):
                warnings.append({
                    "id": EntityId.new().value,
                    "release_schedule_id": schedule.id,
                    "cycle": new_cycle,
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
                        "release_cycle": new_cycle,
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
                    cycle=new_cycle,
                )
            )
            await self.uow.commit()

        logger.info("release_schedule_restarted", payment_id=payment.id, cycle=new_cycle)
        return True
