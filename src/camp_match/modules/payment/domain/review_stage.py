"""Review stage and next action domain logic."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from camp_match.modules.payment.domain.value_objects import (
    DisputeStatus,
    FundDispositionStatus,
    ReviewNextAction,
    ReviewStage,
)


def derive_review_stage_and_action(
    fund_disposition: Any | None,
    operations: list[Any],
    dispute_status: DisputeStatus | None,
    booking_status: str | None,
    handover_status: Any | None,
    student_confirmed_at: datetime | None,
) -> tuple[ReviewStage, ReviewNextAction]:
    # 1. Reconciliation required
    disp_status = getattr(fund_disposition, "status", None)
    if disp_status == FundDispositionStatus.RECONCILIATION_REQUIRED or any(
        getattr(op, "status", None) == "RECONCILIATION_REQUIRED" for op in operations
    ):
        return ReviewStage.RECONCILIATION_REQUIRED, ReviewNextAction.RECONCILE_OPERATION

    # 2. Open dispute
    if dispute_status == DisputeStatus.OPEN:
        return ReviewStage.DISPUTED, ReviewNextAction.RESOLVE_DISPUTE

    # 3. Settled (no remaining balance or disposition settled)
    remaining_kobo = getattr(fund_disposition, "remaining_releasable_kobo", None)
    released_kobo = getattr(fund_disposition, "released_kobo", 0)
    refunded_kobo = getattr(fund_disposition, "refunded_kobo", 0)

    # Check if settled / zero remaining
    is_settled = (
        disp_status in (FundDispositionStatus.RELEASED, FundDispositionStatus.REFUNDED)
        or (remaining_kobo is not None and remaining_kobo <= 0)
        or (released_kobo > 0 and refunded_kobo == 0 and remaining_kobo == 0)
    )
    if is_settled or disp_status in (
        FundDispositionStatus.RELEASED,
        FundDispositionStatus.REFUNDED,
    ):
        if released_kobo > 0 and refunded_kobo > 0:
            return ReviewStage.SETTLED_SPLIT, ReviewNextAction.NONE
        if refunded_kobo > 0:
            return ReviewStage.REFUNDED, ReviewNextAction.NONE
        if released_kobo > 0 or disp_status == FundDispositionStatus.RELEASED:
            return ReviewStage.RELEASED, ReviewNextAction.NONE

    # 4. Booking closed and funds held
    is_closed = booking_status in ("CANCELLED", "EXPIRED", "INVALIDATED")
    if is_closed and (remaining_kobo is None or remaining_kobo > 0):
        return ReviewStage.BOOKING_CLOSED_FUNDS_HELD, ReviewNextAction.DECIDE_REFUND

    # 5. Student confirmed -> release due
    if student_confirmed_at is not None:
        return ReviewStage.RELEASE_DUE, ReviewNextAction.RELEASE_FUNDS

    # 6. Handover offered -> awaiting student confirmation
    offered_at = getattr(handover_status, "offered_at", None)
    if offered_at is not None:
        return ReviewStage.AWAITING_STUDENT_CONFIRMATION, ReviewNextAction.NONE

    # 7. Otherwise
    return ReviewStage.AWAITING_HANDOVER_OFFER, ReviewNextAction.NONE
