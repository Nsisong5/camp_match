"""Release policy domain logic."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from camp_match.modules.payment.domain.value_objects import (
    MIN_RELEASE_WARNINGS,
    DisputeStatus,
    EvaluationMode,
)


@dataclass(frozen=True, slots=True)
class HandoverStatusSnapshot:
    offered_at: datetime | None
    accepted_at: datetime | None


@dataclass(frozen=True, slots=True)
class ReleaseEvaluation:
    eligible: bool
    blocking_reason: str | None = None
    student_confirmed_at: datetime | None = None
    earliest_auto_release_at: datetime | None = None


def compute_student_confirmed_at(
    offered_at: datetime | None,
    accepted_at: datetime | None,
) -> datetime | None:
    if offered_at is not None and accepted_at is not None and accepted_at >= offered_at:
        return accepted_at
    return None


def compute_earliest_auto_release_at(
    schedule: Any | None,
    delay_hours: int,
    final_warning_lead_minutes: int,
) -> datetime | None:
    if schedule is None or getattr(schedule, "window_starts_at", None) is None:
        return None
    window_end = schedule.window_starts_at + timedelta(hours=delay_hours)
    warnings = getattr(schedule, "warnings", [])
    sent_warnings = [
        w for w in warnings
        if getattr(w, "sent_at", None) is not None and getattr(w, "superseded_at", None) is None
    ]
    if len(sent_warnings) < MIN_RELEASE_WARNINGS:
        return None
    last_sent = max(w.sent_at for w in sent_warnings)
    lead = timedelta(minutes=final_warning_lead_minutes)
    return max(window_end, last_sent + lead)


def evaluate_release_eligibility(
    fund_disposition: Any | None,
    booking_summary: Any | None,
    handover_status: Any | None,
    dispute_status: DisputeStatus | None,
    requested_amount_kobo: int,
    schedule: Any | None = None,
    approvers_available: int = 1,
    mode: EvaluationMode = EvaluationMode.MANUAL,
    clock_now: datetime | None = None,
    settings_view: Any | None = None,
    fallback_window_hours: int | None = None,
) -> ReleaseEvaluation:
    if settings_view is None and fallback_window_hours is not None:
        class DummySettings:
            payment_auto_release_delay_hours = fallback_window_hours
            payment_release_warning_final_warning_min_lead_minutes = 60
        settings_view = DummySettings()
    elif settings_view is None:
        class DummySettings:
            payment_auto_release_delay_hours = 48
            payment_release_warning_final_warning_min_lead_minutes = 60
        settings_view = DummySettings()
    offered_at = getattr(handover_status, "offered_at", None)
    accepted_at = getattr(handover_status, "accepted_at", None)
    student_confirmed_at = compute_student_confirmed_at(offered_at, accepted_at)

    delay_hours = getattr(settings_view, "payment_auto_release_delay_hours", 48)
    lead_minutes = getattr(
        settings_view, "payment_release_warning_final_warning_min_lead_minutes", 60
    )
    earliest_auto = compute_earliest_auto_release_at(schedule, delay_hours, lead_minutes)

    # Condition 1: Confirmed payment and fund disposition exist
    if fund_disposition is None:
        return ReleaseEvaluation(
            eligible=False,
            blocking_reason="no_confirmed_payment",
            student_confirmed_at=student_confirmed_at,
            earliest_auto_release_at=earliest_auto,
        )

    # Condition 2: Booking is CONFIRMED
    if booking_summary is None or getattr(booking_summary, "status", None) != "CONFIRMED":
        return ReleaseEvaluation(
            eligible=False,
            blocking_reason="booking_not_confirmed",
            student_confirmed_at=student_confirmed_at,
            earliest_auto_release_at=earliest_auto,
        )

    # Condition 3: Handover was offered
    if offered_at is None:
        return ReleaseEvaluation(
            eligible=False,
            blocking_reason="handover_not_offered",
            student_confirmed_at=student_confirmed_at,
            earliest_auto_release_at=earliest_auto,
        )

    # Condition 4: Student confirmation required
    if student_confirmed_at is None:
        return ReleaseEvaluation(
            eligible=False,
            blocking_reason="student_confirmation_required",
            student_confirmed_at=student_confirmed_at,
            earliest_auto_release_at=earliest_auto,
        )

    # Condition 5: No open dispute
    if dispute_status == DisputeStatus.OPEN:
        return ReleaseEvaluation(
            eligible=False,
            blocking_reason="dispute_open",
            student_confirmed_at=student_confirmed_at,
            earliest_auto_release_at=earliest_auto,
        )

    # Condition 6: requested_amount <= remaining_releasable and > 0
    remaining = getattr(fund_disposition, "remaining_releasable_kobo", 0)
    if requested_amount_kobo <= 0 or requested_amount_kobo > remaining:
        return ReleaseEvaluation(
            eligible=False,
            blocking_reason="amount_exceeds_remaining_balance",
            student_confirmed_at=student_confirmed_at,
            earliest_auto_release_at=earliest_auto,
        )

    # If manual mode, conditions 1-6 are sufficient
    if mode == EvaluationMode.MANUAL:
        return ReleaseEvaluation(
            eligible=True,
            blocking_reason=None,
            student_confirmed_at=student_confirmed_at,
            earliest_auto_release_at=earliest_auto,
        )

    # Automatic mode conditions (7-11)
    # Condition 7: Release schedule exists
    if schedule is None or getattr(schedule, "window_starts_at", None) is None:
        return ReleaseEvaluation(
            eligible=False,
            blocking_reason="release_schedule_missing",
            student_confirmed_at=student_confirmed_at,
            earliest_auto_release_at=earliest_auto,
        )

    # Condition 8: window_starts_at + delay elapsed
    window_starts_at = schedule.window_starts_at
    auto_release_time = window_starts_at + timedelta(hours=delay_hours)
    if clock_now < auto_release_time:
        return ReleaseEvaluation(
            eligible=False,
            blocking_reason="auto_release_window_not_elapsed",
            student_confirmed_at=student_confirmed_at,
            earliest_auto_release_at=earliest_auto,
        )

    # Condition 9: Active warnings count >= MIN_RELEASE_WARNINGS and all sent
    warnings = getattr(schedule, "warnings", [])
    active_warnings = [
        w for w in warnings
        if getattr(w, "superseded_at", None) is None
    ]
    has_unsent = any(getattr(w, "sent_at", None) is None for w in active_warnings)
    if len(active_warnings) < MIN_RELEASE_WARNINGS or has_unsent:
        return ReleaseEvaluation(
            eligible=False,
            blocking_reason="release_warnings_pending",
            student_confirmed_at=student_confirmed_at,
            earliest_auto_release_at=earliest_auto,
        )

    # Condition 10: clock_now >= last_warning_sent_at + final_warning_min_lead
    last_sent_at = max(w.sent_at for w in active_warnings)
    lead_time = last_sent_at + timedelta(minutes=lead_minutes)
    if clock_now < lead_time:
        return ReleaseEvaluation(
            eligible=False,
            blocking_reason="final_warning_too_recent",
            student_confirmed_at=student_confirmed_at,
            earliest_auto_release_at=earliest_auto,
        )

    # Condition 11: At least one active release approver exists
    if approvers_available < 1:
        return ReleaseEvaluation(
            eligible=False,
            blocking_reason="no_release_approver_available",
            student_confirmed_at=student_confirmed_at,
            earliest_auto_release_at=earliest_auto,
        )

    return ReleaseEvaluation(
        eligible=True,
        blocking_reason=None,
        student_confirmed_at=student_confirmed_at,
        earliest_auto_release_at=earliest_auto,
    )
