from __future__ import annotations

from datetime import datetime

from camp_match.modules.admin_operations.domain.value_objects import IssueStatus

MANAGEABLE_STAFF_ROLES: frozenset[str] = frozenset(["OPERATIONS"])


def is_manageable(role: str) -> bool:
    return role in MANAGEABLE_STAFF_ROLES


def is_uncertain(
    request_event_occurred_at: datetime,
    outcome_exists: bool,
    now: datetime,
    threshold_seconds: int,
) -> bool:
    if outcome_exists:
        return False
    age_seconds = (now - request_event_occurred_at).total_seconds()
    return age_seconds > threshold_seconds


def can_reassign(status: IssueStatus) -> bool:
    return status in {IssueStatus.OPEN, IssueStatus.IN_PROGRESS, IssueStatus.AWAITING_INFORMATION}
