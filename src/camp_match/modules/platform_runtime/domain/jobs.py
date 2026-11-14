from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class JobHealth(StrEnum):
    OK = "OK"
    FAILING = "FAILING"
    STALE = "STALE"
    DISABLED = "DISABLED"
    NEVER_RAN = "NEVER_RAN"


@dataclass(frozen=True)
class JobDefinition:
    name: str
    interval_seconds: int
    default_enabled: bool = True


def derive_job_health(
    name: str,
    disabled_jobs: set[str],
    last_finished_at: datetime | None,
    consecutive_failures: int,
    failing_threshold: int,
    interval_seconds: int,
    stale_multiplier: int,
    now: datetime,
) -> str:
    if name in disabled_jobs:
        return JobHealth.DISABLED
    if last_finished_at is None:
        return JobHealth.NEVER_RAN
    if consecutive_failures >= failing_threshold:
        return JobHealth.FAILING
    elapsed = (now - last_finished_at).total_seconds()
    if elapsed > (interval_seconds * stale_multiplier):
        return JobHealth.STALE
    return JobHealth.OK
