"""Dispatch release warnings use case."""
from __future__ import annotations

import structlog
from datetime import datetime

from camp_match.modules.payment.application.ports.outbound import (
    DisputeRepository,
    ReleaseApproverProvider,
    ReleaseScheduleRepository,
    TransactionReviewRepository,
)
from camp_match.modules.payment.domain.events import PaymentAutoReleaseWarning
from camp_match.modules.payment.domain.value_objects import DisputeStatus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock

logger = structlog.get_logger(__name__)


class DispatchReleaseWarningsUseCase:
    def __init__(
        self,
        schedule_repo: ReleaseScheduleRepository,
        review_repo: TransactionReviewRepository,
        dispute_repo: DisputeRepository,
        approver_provider: ReleaseApproverProvider,
        uow: UnitOfWork,
        clock: Clock,
        settings_view: Any,
    ) -> None:
        self.schedule_repo = schedule_repo
        self.review_repo = review_repo
        self.dispute_repo = dispute_repo
        self.approver_provider = approver_provider
        self.uow = uow
        self.clock = clock
        self.settings_view = settings_view

    async def execute(self) -> dict[str, int]:
        now = self.clock.now()
        dispatched = 0
        skipped = 0

        approvers_count = await self.approver_provider.count_active_approvers()
        if approvers_count == 0:
            logger.warning("dispatch_release_warnings_skipped_no_approvers")
            return {"dispatched": 0, "skipped": 0}

        min_spacing_minutes = getattr(self.settings_view, "payment_release_warning_min_spacing_minutes", 60)
        schedules = await self.schedule_repo.list_all() if hasattr(self.schedule_repo, "list_all") else []

        for schedule in schedules:
            dispute = await self.dispute_repo.get_open_by_fund_disposition_id(schedule.fund_disposition_id)
            if dispute and dispute.status == DisputeStatus.OPEN:
                skipped += 1
                continue

            claimed = await self.schedule_repo.claim_warning(
                schedule_id=schedule.id,
                cycle=schedule.cycle,
                now=now,
                min_spacing_minutes=min_spacing_minutes,
            )
            if claimed:
                review = await self.review_repo.get_by_payment_id(schedule.payment_id)
                async with self.uow:
                    if review:
                        warnings_sent = (review.warnings_sent or 0) + 1
                        await self.review_repo.update_conditional(
                            payment_id=schedule.payment_id,
                            expected_version=review.version,
                            values={"warnings_sent": warnings_sent},
                        )
                    
                    event = PaymentAutoReleaseWarning(
                        payment_id=schedule.payment_id,
                        booking_id=schedule.booking_id,
                        student_id=review.student_id if review else schedule.booking_id,
                        cycle=schedule.cycle,
                        warning_stage=str(claimed.warning_number),
                    )
                    self.uow.add_event(event)
                    await self.uow.commit()

                dispatched += 1
                logger.info(
                    "release_warning_dispatched",
                    schedule_id=schedule.id,
                    cycle=schedule.cycle,
                    warning_number=claimed.warning_number,
                )
            else:
                skipped += 1

        return {"dispatched": dispatched, "skipped": skipped}
