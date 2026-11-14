from __future__ import annotations

from typing import Any

from camp_match.modules.platform_runtime.adapters.persistence.job_repository import SqlAlchemyJobRepository
from camp_match.modules.platform_runtime.adapters.persistence.outbox_repository import SqlAlchemyOutboxRepository
from camp_match.modules.platform_runtime.application.use_cases.get_job_statuses import GetJobStatusesUseCase
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessPlatformRuntimeProvider:
    def __init__(
        self,
        session_factory: Any,
        clock: Any,
        settings: Any,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._settings = settings

    async def get_job_statuses(self) -> list[Any]:
        get_statuses_uc = GetJobStatusesUseCase(
            session_factory=self._session_factory,
            job_repo_factory=SqlAlchemyJobRepository,
            clock=self._clock,
            settings=self._settings,
        )
        return await get_statuses_uc.execute()

    async def get_outbox_stats(self) -> dict[str, Any]:
        async with self._session_factory() as session:
            outbox_repo = SqlAlchemyOutboxRepository(session)
            stats = await outbox_repo.stats()
            await session.commit()
            return stats


class InProcessPlatformRecovery:
    def __init__(self, session_factory: Any, clock: Any) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def requeue_dead(self, actor_id: EntityId) -> int:
        now = self._clock.now()
        async with self._session_factory() as session:
            outbox_repo = SqlAlchemyOutboxRepository(session)
            count = await outbox_repo.requeue_dead(now)
            await session.commit()
            return count
