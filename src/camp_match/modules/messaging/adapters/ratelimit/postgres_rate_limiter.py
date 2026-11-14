from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.modules.messaging.adapters.persistence.models import PlatformRateLimitModel
from camp_match.modules.messaging.application.ports.outbound import RateLimitResult
from camp_match.platform.clock import SystemClock


class PostgresRateLimiter:
    def __init__(self, session_factory: Any, clock: Any | None = None) -> None:
        self._session_factory = session_factory
        self._clock = clock or SystemClock()

    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now_dt = self._clock.now()
        now_ts = int(now_dt.timestamp())
        window_start_ts = (now_ts // window_seconds) * window_seconds
        window_start = datetime.fromtimestamp(window_start_ts, UTC)

        async with self._session_factory() as session:
            stmt = (
                insert(PlatformRateLimitModel)
                .values(
                    key=key,
                    window_start=window_start,
                    count=1,
                )
                .on_conflict_do_update(
                    index_elements=["key", "window_start"],
                    set_={"count": PlatformRateLimitModel.count + 1},
                )
                .returning(PlatformRateLimitModel.count)
            )
            res = await session.execute(stmt)
            count = res.scalar_one()
            await session.commit()

        allowed = count <= limit
        if not allowed:
            end_of_window = window_start + timedelta(seconds=window_seconds)
            retry_after = int(math.ceil((end_of_window - now_dt).total_seconds()))
            return RateLimitResult(allowed=False, retry_after_seconds=max(1, retry_after))

        return RateLimitResult(allowed=True, retry_after_seconds=0)

    async def purge_old_windows(self, cutoff: datetime, limit: int = 500) -> int:
        async with self._session_factory() as session:
            subq = (
                select(PlatformRateLimitModel.key)
                .where(PlatformRateLimitModel.window_start < cutoff)
                .limit(limit)
                .scalar_subquery()
            )
            stmt = delete(PlatformRateLimitModel).where(
                PlatformRateLimitModel.window_start < cutoff,
                PlatformRateLimitModel.key.in_(subq),
            )
            res = await session.execute(stmt)
            await session.commit()
            return int(res.rowcount)
