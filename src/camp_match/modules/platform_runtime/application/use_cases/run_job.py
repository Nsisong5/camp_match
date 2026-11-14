from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from camp_match.modules.platform_runtime.domain.outbox import calculate_backoff
from camp_match.shared_kernel.domain.clock import Clock

logger = structlog.get_logger()


class RunJobUseCase:
    def __init__(
        self,
        session_factory: Any,
        job_repo_factory: Any,
        clock: Clock,
        settings: Any,
    ) -> None:
        self._session_factory = session_factory
        self._job_repo_factory = job_repo_factory
        self._clock = clock
        self._settings = settings

    async def execute(
        self,
        name: str,
        interval_seconds: int,
        job_fn: Callable[[], Coroutine[Any, Any, None]],
        lease_holder: str,
    ) -> str:
        now = self._clock.now() if self._clock else datetime.now(UTC)
        timeout_seconds = getattr(
            self._settings, "platform_worker_job_timeout_seconds", 120
        )
        cap_seconds = getattr(
            self._settings, "platform_job_failure_backoff_cap_seconds", 300
        )
        base_seconds = getattr(
            self._settings, "platform_outbox_backoff_base_seconds", 5
        )

        async with self._session_factory() as session:
            job_repo = self._job_repo_factory(session)
            await job_repo.ensure_job(name, interval_seconds, now)

            lease_expires_at = now + timedelta(seconds=timeout_seconds)
            acquired = await job_repo.try_acquire(
                name, lease_holder, lease_expires_at, now
            )
            if not acquired:
                await session.commit()
                return "NOT_DUE_OR_LEASED"

            await session.commit()

        started_at = now
        try:
            async with asyncio.timeout(timeout_seconds):
                await job_fn()

            finished_at = (
                self._clock.now() if self._clock else datetime.now(UTC)
            )
            next_run_at = finished_at + timedelta(seconds=interval_seconds)

            async with self._session_factory() as session:
                job_repo = self._job_repo_factory(session)
                await job_repo.record_success(
                    name, started_at, finished_at, next_run_at
                )
                await session.commit()
            return "SUCCESS"
        except Exception as exc:
            finished_at = (
                self._clock.now() if self._clock else datetime.now(UTC)
            )
            backoff = calculate_backoff(1, base_seconds, cap_seconds)
            next_run_at = finished_at + timedelta(seconds=backoff)

            async with self._session_factory() as session:
                job_repo = self._job_repo_factory(session)
                await job_repo.record_failure(
                    name, started_at, str(exc), next_run_at
                )
                await session.commit()
            logger.warning("job_execution_failed", job_name=name, error=str(exc))
            return "FAILED"
