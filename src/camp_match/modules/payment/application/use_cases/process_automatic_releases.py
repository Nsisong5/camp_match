from __future__ import annotations

import structlog
from typing import Any

from camp_match.modules.payment.application.ports.outbound import (
    BookingProvider,
    DisputeRepository,
    FundDispositionRepository,
    ReleaseApproverProvider,
    ReleaseDecisionRepository,
    ReleaseScheduleRepository,
    TransactionReviewRepository,
)
from camp_match.modules.payment.application.use_cases.execute_release import ExecuteReleaseUseCase
from camp_match.modules.payment.domain.release_policy import (
    HandoverStatusSnapshot,
    evaluate_release_eligibility,
)
from camp_match.modules.payment.domain.value_objects import (
    DisputeStatus,
    EvaluationMode,
    FundDispositionStatus,
    Money,
    ReviewStage,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger(__name__)


class ProcessAutomaticReleasesUseCase:
    def __init__(
        self,
        fund_disposition_repo: FundDispositionRepository,
        booking_provider: BookingProvider,
        dispute_repo: DisputeRepository,
        schedule_repo: ReleaseScheduleRepository,
        review_repo: TransactionReviewRepository,
        approver_provider: ReleaseApproverProvider,
        release_decision_repo: ReleaseDecisionRepository,
        execute_release_use_case: ExecuteReleaseUseCase,
        uow: UnitOfWork,
        clock: Clock,
        settings_view: Any,
    ) -> None:
        self.fund_disposition_repo = fund_disposition_repo
        self.booking_provider = booking_provider
        self.dispute_repo = dispute_repo
        self.schedule_repo = schedule_repo
        self.review_repo = review_repo
        self.approver_provider = approver_provider
        self.release_decision_repo = release_decision_repo
        self.execute_release_use_case = execute_release_use_case
        self.uow = uow
        self.clock = clock
        self.settings_view = settings_view

    async def execute(self) -> dict[str, int]:
        now = self.clock.now()
        processed = 0
        released = 0
        skipped = 0

        reviews = await self.review_repo.list_reviews({"stage": ReviewStage.RELEASE_DUE.value}, limit=100, offset=0)
        approvers_count = await self.approver_provider.count_active_approvers()

        for review in reviews:
            processed += 1
            fd = await self.fund_disposition_repo.get_by_payment_id(review.payment_id)
            if not fd or fd.status != FundDispositionStatus.HELD:
                skipped += 1
                continue

            booking = await self.booking_provider.get_booking(fd.booking_id)
            dispute = await self.dispute_repo.get_open_by_fund_disposition_id(fd.id)
            dispute_status = DisputeStatus(dispute.status) if dispute else None
            schedule = await self.schedule_repo.get_by_fund_disposition_id(fd.id)

            handover_snapshot = HandoverStatusSnapshot(
                offered_at=booking.handover_offered_at if booking else None,
                accepted_at=booking.handover_accepted_at if booking else None,
            )

            evaluation = evaluate_release_eligibility(
                fund_disposition=fd,
                booking_summary=booking,
                handover_status=handover_snapshot,
                dispute_status=dispute_status,
                requested_amount_kobo=fd.remaining_releasable_kobo,
                schedule=schedule,
                approvers_available=approvers_count,
                mode=EvaluationMode.AUTOMATIC,
                clock_now=now,
                settings_view=self.settings_view,
            )

            if evaluation.eligible and evaluation.student_confirmed_at is not None:
                decision_id = EntityId.new()
                async with self.uow:
                    await self.release_decision_repo.add(
                        decision_id=decision_id,
                        fund_disposition_id=fd.id,
                        decision="RELEASE",
                        amount_kobo=fd.remaining_releasable_kobo,
                        currency="NGN",
                        policy_version="1.0",
                        triggering_fact="automatic_after_confirmation_window",
                        origin="AUTOMATIC",
                        reason="Automatic release after confirmation window",
                        decided_at=now,
                        student_confirmed_at=evaluation.student_confirmed_at,
                        warnings_sent_count=schedule.warnings_sent_count if schedule else (review.warnings_sent or 3),
                    )
                    await self.uow.commit()

                await self.execute_release_use_case.execute(
                    decision_id=decision_id,
                    fund_disposition_id=fd.id,
                    amount=Money(fd.remaining_releasable_kobo),
                    recipient_reference="automatic_payout_ref",
                )
                released += 1
                logger.info("automatic_release_executed", payment_id=review.payment_id, decision_id=decision_id)
            else:
                skipped += 1

        logger.info(
            "process_automatic_releases_run_completed",
            processed=processed,
            released=released,
            skipped=skipped,
        )
        return {"processed": processed, "released": released, "skipped": skipped}
