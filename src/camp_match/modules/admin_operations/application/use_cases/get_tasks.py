"""Get tasks use case."""
from __future__ import annotations

import asyncio
import structlog
from typing import Any

from camp_match.modules.admin_operations.application.ports.inbound import (
    GetTasksRequest,
    TaskSectionView,
    TasksView,
    TaskView,
)
from camp_match.modules.admin_operations.application.ports.outbound import TaskSource
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class GetTasksUseCase:
    def __init__(
        self,
        task_sources: dict[str, TaskSource],
        authorizer: Any,
        clock: Any,
        settings: Any,
    ) -> None:
        self._task_sources = task_sources
        self._authorizer = authorizer
        self._clock = clock
        self._settings = settings

    async def execute(self, request: GetTasksRequest) -> TasksView:
        if request.limit_per_source is not None and (request.limit_per_source <= 0 or request.limit_per_source > 100):
            raise ValueError("limit_per_source must be between 1 and 100")

        await self._authorizer.authorize(request.actor_id, Permission.ADMIN_OVERVIEW_VIEW)

        now = self._clock.now()
        timeout = getattr(self._settings, "admin_overview_section_timeout_seconds", 3.0)
        limit = request.limit_per_source or getattr(self._settings, "admin_tasks_per_source_limit_default", 20)

        requested_sources = request.sources if request.sources else list(self._task_sources.keys())
        filters = {
            "types": request.types,
            "priority": request.priority,
        }

        async def fetch_source_tasks(name: str, source: TaskSource) -> TaskSectionView:
            try:
                # C7: each source in its own short-lived session (managed by the adapter if needed)
                # and under timeout.
                section = await asyncio.wait_for(
                    source.fetch(request.actor_id, filters, limit),
                    timeout=timeout
                )
                return TaskSectionView(
                    source=section.source,
                    status=section.status,
                    as_of=section.as_of,
                    items=[
                        TaskView(
                            task_id=item.task_id,
                            type=item.type,
                            priority=item.priority,
                            since=item.since,
                            subject=item.subject,
                            target=item.target,
                            facts=item.facts,
                            required_permission=item.required_permission,
                            can_act=item.can_act,
                            due_at=item.due_at,
                        )
                        for item in section.items
                    ],
                    total=section.total,
                    reason_code=section.reason_code,
                )
            except Exception as e:
                logger.warning("fetch_tasks_source_failed", source=name, error=str(e))
                err_str = str(e).lower()
                is_forbidden = (
                    "forbidden" in err_str
                    or "unauthorized" in err_str
                    or "not permitted" in err_str
                    or isinstance(e, PermissionError)
                    or getattr(e, "code", None) == "forbidden"
                )
                status = "NOT_AUTHORIZED" if is_forbidden else "UNAVAILABLE"
                reason_code = "forbidden" if is_forbidden else None
                return TaskSectionView(
                    source=name,
                    status=status,
                    as_of=now,
                    items=[],
                    total=None,
                    reason_code=reason_code,
                )

        # C7: sequentially fetch each source
        sections = []
        for name in requested_sources:
            if name in self._task_sources:
                sections.append(await fetch_source_tasks(name, self._task_sources[name]))

        return TasksView(as_of=now, sections=sections)
