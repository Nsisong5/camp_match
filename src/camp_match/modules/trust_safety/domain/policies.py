from __future__ import annotations

from datetime import datetime

from camp_match.modules.trust_safety.domain.value_objects import (
    EnforcementType,
    ReportCategory,
    ReportStatus,
)


def status_for_reporter(report_status: ReportStatus) -> str:
    if report_status == ReportStatus.RECEIVED:
        return "Received"
    elif report_status == ReportStatus.LINKED:
        return "Under review"
    elif report_status == ReportStatus.CLOSED:
        return "Reviewed"
    return "Received"


def is_high_impact(action_type: EnforcementType) -> bool:
    return action_type != EnforcementType.WARNING


def validate_restriction_end(
    ends_at: datetime, now: datetime, max_days: int = 365
) -> bool:
    if ends_at <= now:
        return False
    delta = ends_at - now
    return not delta.days > max_days


def backoff_delay_seconds(attempts: int, base: int = 30, cap: int = 3600) -> int:
    if attempts < 1:
        raise ValueError("Attempts must be at least 1.")
    delay = int(base * (2 ** (attempts - 1)))
    return min(delay, cap)


def queue_sort_key(category: ReportCategory, created_at: datetime) -> tuple[int, datetime]:
    prio = 0 if category == ReportCategory.THREAT_OR_DANGER else 1
    return (prio, created_at)
