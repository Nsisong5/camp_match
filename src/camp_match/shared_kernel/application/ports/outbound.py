from __future__ import annotations

from typing import Protocol

from camp_match.shared_kernel.domain.identifiers import EntityId


class OutboxNudge(Protocol):
    async def nudge(self, event_ids: list[EntityId]) -> None: ...
