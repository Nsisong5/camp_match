from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.modules.platform_runtime.adapters.persistence.job_models import (
    PlatformJobModel,
)
from camp_match.modules.platform_runtime.application.ports.outbound import (
    JobStatusRecord,
)
from camp_match.modules.platform_runtime.domain.jobs import derive_job_health


class SqlAlchemyJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_job(
        self, name: str, interval_seconds: int, now: datetime
    ) -> None:
        stmt = insert(PlatformJobModel).values(
            name=name,
            enabled=True,
            interval_seconds=interval_seconds,
            next_run_at=now,
            consecutive_failures=0,
        ).on_conflict_do_nothing(index_elements=["name"])
        await self._session.execute(stmt)

    async def try_acquire(
        self,
        name: str,
        lease_holder: str,
        lease_expires_at: datetime,
        now: datetime,
    ) -> bool:
        stmt = (
            update(PlatformJobModel)
            .where(
                PlatformJobModel.name == name,
                PlatformJobModel.enabled,
                PlatformJobModel.next_run_at <= now,
                or_(
                    PlatformJobModel.lease_expires_at.is_(None),
                    PlatformJobModel.lease_expires_at <= now,
                    PlatformJobModel.lease_holder == lease_holder,
                ),
            )
            .values(
                last_started_at=now,
                lease_holder=lease_holder,
                lease_expires_at=lease_expires_at,
            )
        )
        result = await self._session.execute(stmt)
        return (cast(Any, result).rowcount or 0) > 0

    async def record_success(
        self,
        name: str,
        started_at: datetime,
        finished_at: datetime,
        next_run_at: datetime,
    ) -> None:
        stmt = (
            update(PlatformJobModel)
            .where(PlatformJobModel.name == name)
            .values(
                last_finished_at=finished_at,
                next_run_at=next_run_at,
                lease_holder=None,
                lease_expires_at=None,
                consecutive_failures=0,
                last_error=None,
            )
        )
        await self._session.execute(stmt)

    async def record_failure(
        self,
        name: str,
        started_at: datetime,
        error: str,
        next_run_at: datetime,
    ) -> None:
        stmt = (
            update(PlatformJobModel)
            .where(PlatformJobModel.name == name)
            .values(
                last_finished_at=started_at,
                next_run_at=next_run_at,
                lease_holder=None,
                lease_expires_at=None,
                consecutive_failures=PlatformJobModel.consecutive_failures + 1,
                last_error=error[:255],
            )
        )
        await self._session.execute(stmt)

    async def list_statuses(
        self,
        disabled_jobs: set[str],
        stale_multiplier: int,
        failing_threshold: int,
        now: datetime,
    ) -> list[JobStatusRecord]:
        stmt = select(PlatformJobModel).order_by(PlatformJobModel.name)
        result = await self._session.execute(stmt)
        jobs = result.scalars().all()
        records = []
        for j in jobs:
            health = derive_job_health(
                name=j.name,
                disabled_jobs=disabled_jobs,
                last_finished_at=j.last_finished_at,
                consecutive_failures=j.consecutive_failures,
                failing_threshold=failing_threshold,
                interval_seconds=j.interval_seconds,
                stale_multiplier=stale_multiplier,
                now=now,
            )
            records.append(
                JobStatusRecord(
                    name=j.name,
                    enabled=j.enabled,
                    interval_seconds=j.interval_seconds,
                    last_started_at=j.last_started_at,
                    last_finished_at=j.last_finished_at,
                    next_run_at=j.next_run_at,
                    lease_holder=j.lease_holder,
                    lease_expires_at=j.lease_expires_at,
                    consecutive_failures=j.consecutive_failures,
                    last_error=j.last_error,
                    health=health,
                )
            )
        return records
