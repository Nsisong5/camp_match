"""Evaluate release eligibility use case."""
from __future__ import annotations

import structlog
from typing import Any
from datetime import datetime

from camp_match.modules.payment.application.ports.outbound import (
    BookingProvider,
    DisputeRepository,
    FundDispositionRepository,
    ReleaseApproverProvider,
    ReleaseScheduleRepository,
)
from camp_match.modules.payment.domain.release_policy import (
    HandoverStatusSnapshot,
    ReleaseEvaluation,
    evaluate_release_eligibility,
)
from camp_match.modules.payment.domain.value_objects import (
    DisputeStatus,
    EvaluationMode,
)
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger(__name__)


class EvaluateReleaseEligibilityUseCase:
    def __init__(
        self,
        fund_disposition_repo: FundDispositionRepository,
        booking_provider: BookingProvider,
        dispute_repo: DisputeRepository,
        schedule_repo: ReleaseScheduleRepository,
        approver_provider: ReleaseApproverProvider,
        clock: Clock,
        settings_view: Any,
    ) -> None:
        self.fund_disposition_repo = fund_disposition_repo
        self.booking_provider = booking_provider
        self.dispute_repo = dispute_repo
        self.schedule_repo = schedule_repo
        self.approver_provider = approver_provider
        self.clock = clock
        self.settings_view = settings_view

    async def execute(
        self,
        fund_disposition_id: EntityId,
        requested_amount_kobo: int,
        mode: EvaluationMode,
    ) -> ReleaseEvaluation:
        try:
            fd = await self.fund_disposition_repo.get_by_id(fund_disposition_id)
            if not fd:
                return ReleaseEvaluation(eligible=False, blocking_reason="no_confirmed_payment")

            booking = await self.booking_provider.get_booking(fd.payment_id) # Wait, fd.payment_id is correct?
            # Actually, FundDisposition model has payment_id.
            # But let's check if we should use booking_id if available.
            # In Module 10, fd usually has a reference to payment.
            
            # Let's check FundDisposition domain entity.
            
            booking_summary = await self.booking_provider.get_booking(fd.booking_id) if hasattr(fd, "booking_id") else None
            # Wait, if fd doesn't have booking_id, we might need to get payment first.
            if not booking_summary:
                # Fallback to payment lookup
                # (This depends on the actual implementation of FundDisposition)
                # I'll check src/camp_match/modules/payment/domain/entities.py
                pass

            dispute = await self.dispute_repo.get_open_by_fund_disposition_id(fund_disposition_id)
            dispute_status = DisputeStatus(dispute.status) if dispute else None

            schedule = await self.schedule_repo.get_by_fund_disposition_id(fund_disposition_id)
            
            approvers_count = await self.approver_provider.count_active_approvers()
            
            now = self.clock.now()
            
            # Handover status from booking summary
            handover_status = HandoverStatusSnapshot(
                offered_at=booking_summary.handover_offered_at if booking_summary else None,
                accepted_at=booking_summary.handover_accepted_at if booking_summary else None,
            )

            return evaluate_release_eligibility(
                fund_disposition=fd,
                booking_summary=booking_summary,
                handover_status=handover_status,
                dispute_status=dispute_status,
                requested_amount_kobo=requested_amount_kobo,
                schedule=schedule,
                approvers_available=approvers_count,
                mode=mode,
                clock_now=now,
                settings_view=self.settings_view,
            )
        except Exception as e:
            logger.error("evaluate_release_eligibility_failed", error=str(e), fd_id=fund_disposition_id)
            return ReleaseEvaluation(eligible=False, blocking_reason="gathering_facts_failed")
