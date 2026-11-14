from __future__ import annotations

from typing import Any

from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class GetJobsUseCase:
    def __init__(self, platform_runtime_provider: Any, authorizer: Any) -> None:
        self._provider = platform_runtime_provider
        self._authorizer = authorizer

    async def execute(self, actor_id: EntityId) -> list[Any]:
        await self._authorizer.authorize(actor_id, Permission.ADMIN_OVERVIEW_VIEW)
        return await self._provider.get_job_statuses()
