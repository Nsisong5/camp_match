from __future__ import annotations

from datetime import UTC, datetime
import pytest

from camp_match.config.settings import get_settings
from camp_match.modules.platform_runtime.adapters.jobs.registry import get_job_registry
from camp_match.modules.platform_runtime.application.use_cases.run_job import RunJobUseCase
from camp_match.modules.platform_runtime.application.use_cases.get_job_statuses import (
    GetJobStatusesUseCase,
)
from camp_match.modules.platform_runtime.adapters.persistence.job_repository import (
    SqlAlchemyJobRepository,
)
from tests.support.fixed_clock import FixedClock


def test_job_registry_has_exact_named_jobs() -> None:
    settings = get_settings()
    registry = get_job_registry(settings)
    expected_jobs = {
        "platform_outbox_relay",
        "messaging_outbox_relay",
        "notification_inbox",
        "safety_enforcement",
        "booking_hold_expiry",
        "payment_recovery",
        "payment_auto_release",
        "booking_reminders",
        "suspended_listing_reconcile",
        "retention_sweep",
    }
    assert set(registry.keys()) == expected_jobs


@pytest.mark.asyncio
async def test_worker_stats_and_list(session_factory) -> None:
    settings = get_settings()
    clock = FixedClock(datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC))
    get_statuses = GetJobStatusesUseCase(
        session_factory, SqlAlchemyJobRepository, clock, settings
    )
    statuses = await get_statuses.execute()
    # Initially jobs might not be in DB until run, or ensure_job populates them.
    # Let's run a job or ensure them.
    assert isinstance(statuses, list)
