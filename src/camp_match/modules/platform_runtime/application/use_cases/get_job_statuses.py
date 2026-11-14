from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from camp_match.modules.platform_runtime.application.ports.outbound import (
    JobStatusRecord,
)


class GetJobStatusesUseCase:
    def __init__(
        self,
        session_factory: Any,
        job_repo_factory: Any,
        clock: Any,
        settings: Any,
    ) -> None:
        self._session_factory = session_factory
        self._job_repo_factory = job_repo_factory
        self._clock = clock
        self._settings = settings

    async def execute(self) -> list[JobStatusRecord]:
        now = self._clock.now() if self._clock else datetime.now(UTC)
        disabled_str = getattr(self._settings, "platform_jobs_disabled", "")
        disabled_jobs = {
            j.strip() for j in disabled_str.split(",") if j.strip()
        }
        stale_multiplier = getattr(
            self._settings, "platform_job_stale_after_multiplier", 3
        )
        failing_threshold = getattr(
            self._settings, "platform_job_failing_after_failures", 3
        )

        async with self._session_factory() as session:
            job_repo = self._job_repo_factory(session)
            statuses = await job_repo.list_statuses(
                disabled_jobs=disabled_jobs,
                stale_multiplier=stale_multiplier,
                failing_threshold=failing_threshold,
                now=now,
            )
            await session.commit()
            return cast(list[JobStatusRecord], statuses)
