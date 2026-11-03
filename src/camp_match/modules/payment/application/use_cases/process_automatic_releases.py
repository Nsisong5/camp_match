from __future__ import annotations

import structlog

from camp_match.modules.payment.application.ports.outbound import (
    BookingProvider,
    FundDispositionRepository,
    ReleaseDecisionRepository,
)
from camp_match.modules.payment.application.use_cases.execute_release import ExecuteReleaseUseCase
from camp_match.modules.payment.domain.release_policy import (
    HandoverStatusSnapshot,
    evaluate_release_eligibility,
)
from camp_match.modules.payment.domain.value_objects import (
    DisputeStatus,
    FundDispositionStatus,
    Money,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class ProcessAutomaticReleasesUseCase:
    def __init__(
        self,
        fund_disposition_repo: FundDispositionRepository,
        booking_provider: BookingProvider,
        release_decision_repo: ReleaseDecisionRepository,
        execute_release_use_case: ExecuteReleaseUseCase,
        fallback_window_hours: int,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.fund_disposition_repo = fund_disposition_repo
        self.booking_provider = booking_provider
        self.release_decision_repo = release_decision_repo
        self.execute_release_use_case = execute_release_use_case
        self.fallback_window_hours = fallback_window_hours
        self.uow = uow
        self.clock = clock

    async def execute(self, dispositions: list, bookings_map: dict, handovers_map: dict, disputes_map: dict) -> dict[str, int]:
        now = self.clock.now()
        processed = 0
        released = 0
        skipped = 0

        for fd in dispositions:
            if fd.status != FundDispositionStatus.HELD:
                skipped += 1
                continue

            processed += 1
            booking = bookings_map.get(fd.payment_id) # or via booking_id
            handover = handovers_map.get(getattr(booking, "id", None))
            dispute = disputes_map.get(fd.id)

            handover_snapshot = HandoverStatusSnapshot(
                offered_at=getattr(handover, "handover_offered_at", None),
                accepted_at=getattr(handover, "handover_accepted_at", None),
            )
            dispute_status = DisputeStatus(dispute.status) if dispute else None

            evaluation = evaluate_release_eligibility(
                fund_disposition=fd,
                booking_summary=booking,
                handover_status=handover_snapshot,
                dispute_status=dispute_status,
                requested_amount_kobo=fd.remaining_releasable_kobo,
                fallback_window_hours=self.fallback_window_hours,
                clock_now=now,
            )

            if evaluation.eligible:
                decision_id = EntityId.new()
                async with self.uow:
                    await self.release_decision_repo.add(
                        decision_id=decision_id,
                        fund_disposition_id=fd.id,
                        decision="RELEASE",
                        amount_kobo=fd.remaining_releasable_kobo,
                        currency="NGN",
                        policy_version="1.0",
                        triggering_fact="automatic_48h_fallback",
                        origin="AUTOMATIC",
                        reason="Automatic 48-hour fallback release",
                        decided_at=now,
                    )
                    await self.uow.commit()

                await self.execute_release_use_case.execute(
                    decision_id=decision_id,
                    fund_disposition_id=fd.id,
                    amount=Money(fd.remaining_releasable_kobo),
                    recipient_reference="automatic_payout_ref",
                )
                released += 1
            else:
                skipped += 1

        logger.info(
            "process_automatic_releases_run_completed",
            processed=processed,
            released=released,
            skipped=skipped,
        )
        return {"processed": processed, "released": released, "skipped": skipped}
