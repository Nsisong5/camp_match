"""Release schedule domain logic."""
from __future__ import annotations

from datetime import datetime, timedelta

from camp_match.modules.payment.domain.value_objects import WarningStage


def compute_warning_due_dates(
    window_starts_at: datetime,
    delay_hours: int,
    offsets_hours: list[int],
) -> list[datetime]:
    window_end = window_starts_at + timedelta(hours=delay_hours)
    return [window_end - timedelta(hours=offset) for offset in offsets_hours]


def get_warning_stage(number: int, total: int) -> WarningStage:
    if number == 1:
        return WarningStage.FIRST
    if number == total:
        return WarningStage.FINAL
    return WarningStage.REMINDER
