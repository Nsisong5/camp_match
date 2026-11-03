from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from camp_match.modules.payment.application.ports.outbound import BookingSummary
from camp_match.modules.payment.domain.entities import FundDisposition
from camp_match.modules.payment.domain.value_objects import DisputeStatus


@dataclass(frozen=True, slots=True)
class HandoverStatusSnapshot:
    offered_at: datetime | None
    accepted_at: datetime | None


@dataclass(frozen=True, slots=True)
class ReleaseEvaluation:
    eligible: bool
    blocking_reason: str | None = None


def evaluate_release_eligibility(
    fund_disposition: FundDisposition | None,
    booking_summary: BookingSummary | None,
    handover_status: HandoverStatusSnapshot | None,
    dispute_status: DisputeStatus | None,
    requested_amount_kobo: int,
    fallback_window_hours: int,
    clock_now: datetime,
) -> ReleaseEvaluation:
    if fund_disposition is None:
        return ReleaseEvaluation(eligible=False, blocking_reason="payment_not_confirmed")

    if booking_summary is None or booking_summary.status == "CANCELLED":
        return ReleaseEvaluation(eligible=False, blocking_reason="booking_cancelled")

    if handover_status is None or handover_status.offered_at is None:
        return ReleaseEvaluation(eligible=False, blocking_reason="handover_not_offered")

    window_elapsed = (clock_now - handover_status.offered_at) >= timedelta(hours=fallback_window_hours)
    accepted = handover_status.accepted_at is not None

    if not accepted and not window_elapsed:
        return ReleaseEvaluation(eligible=False, blocking_reason="awaiting_acceptance_or_window")

    if dispute_status == DisputeStatus.OPEN:
        return ReleaseEvaluation(eligible=False, blocking_reason="dispute_open")

    if requested_amount_kobo > fund_disposition.remaining_releasable_kobo:
        return ReleaseEvaluation(eligible=False, blocking_reason="amount_exceeds_remaining_balance")

    return ReleaseEvaluation(eligible=True)
