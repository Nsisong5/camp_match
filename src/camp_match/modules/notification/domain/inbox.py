"""Inbox retry and status logic."""
from __future__ import annotations

from camp_match.modules.notification.domain.value_objects import InboxStatus


def next_delay_seconds(attempts: int, base: int = 30, cap: int = 3600) -> int:
    if attempts < 1:
        raise ValueError("Attempts must be at least 1.")
    delay = base * (2 ** (attempts - 1))
    return int(min(cap, delay))


def is_terminal(status: InboxStatus) -> bool:
    return status in {InboxStatus.PROCESSED, InboxStatus.REJECTED, InboxStatus.DEAD}
