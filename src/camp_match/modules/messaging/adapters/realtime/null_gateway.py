from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from camp_match.shared_kernel.domain.identifiers import EntityId


class NullRealtimeGateway:
    async def push(self, user_ids: list[EntityId], event: object) -> None:
        pass
