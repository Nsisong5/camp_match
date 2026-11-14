from __future__ import annotations

from datetime import UTC, datetime, timedelta
import asyncio
import pytest

from camp_match.config.settings import get_settings
from camp_match.modules.platform_runtime.adapters.persistence.job_repository import (
    SqlAlchemyJobRepository,
)
from camp_match.modules.platform_runtime.application.use_cases.run_job import RunJobUseCase
from camp_match.modules.platform_runtime.application.use_cases.get_job_statuses import (
    GetJobStatusesUseCase,
)
from tests.support.fixed_clock import FixedClock


@pytest.mark.asyncio
async def test_job_runner_success_flow(session_factory) -> None:
    settings = get_settings()
    clock = FixedClock(datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC))
    run_job = RunJobUseCase(session_factory, SqlAlchemyJobRepository, clock, settings)
    get_statuses = GetJobStatusesUseCase(
        session_factory, SqlAlchemyJobRepository, clock, settings
    )

    executed = []

    async def sample_job() -> None:
        executed.append(True)

    result = await run_job.execute("test_job", 60, sample_job, "worker_1")
    assert result == "SUCCESS"
    assert len(executed) == 1

    statuses = await get_statuses.execute()
    job_status = next(s for s in statuses if s.name == "test_job")
    assert job_status.health == "OK"
    assert job_status.consecutive_failures == 0


@pytest.mark.asyncio
async def test_job_runner_error_swallowed(session_factory) -> None:
    settings = get_settings()
    clock = FixedClock(datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC))
    run_job = RunJobUseCase(session_factory, SqlAlchemyJobRepository, clock, settings)
    get_statuses = GetJobStatusesUseCase(
        session_factory, SqlAlchemyJobRepository, clock, settings
    )

    async def failing_job() -> None:
        raise RuntimeError("Job failed deliberately")

    # Run 3 times, advancing clock between runs
    for i in range(3):
        if i > 0:
            clock._fixed_time += timedelta(seconds=10)
        result = await run_job.execute("failing_job", 1, failing_job, "worker_1")
        assert result == "FAILED"

    statuses = await get_statuses.execute()
    job_status = next(s for s in statuses if s.name == "failing_job")
    assert job_status.health == "FAILING"
    assert job_status.consecutive_failures == 3
    assert "Job failed" in (job_status.last_error or "")


@pytest.mark.asyncio
async def test_job_runner_racing_workers(session_factory) -> None:
    settings = get_settings()
    clock = FixedClock(datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC))
    run_job = RunJobUseCase(session_factory, SqlAlchemyJobRepository, clock, settings)

    async def slow_job() -> None:
        await asyncio.sleep(0.1)

    # Race two workers concurrently for the same due job
    res1, res2 = await asyncio.gather(
        run_job.execute("race_job", 60, slow_job, "worker_A"),
        run_job.execute("race_job", 60, slow_job, "worker_B"),
    )

    # Exactly one should succeed, one should get NOT_DUE_OR_LEASED
    outcomes = {res1, res2}
    assert outcomes == {"SUCCESS", "NOT_DUE_OR_LEASED"}
