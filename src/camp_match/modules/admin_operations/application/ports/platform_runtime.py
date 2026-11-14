"""Platform runtime outbound port and provider adapter."""
from __future__ import annotations

from typing import Any, Protocol


class PlatformRuntimeProvider(Protocol):
    async def get_job_statuses(self) -> list[Any]:
        ...

    async def get_outbox_stats(self) -> dict[str, Any]:
        ...


class PlatformRecovery(Protocol):
    async def requeue_dead(self, actor_id: Any) -> int:
        ...
