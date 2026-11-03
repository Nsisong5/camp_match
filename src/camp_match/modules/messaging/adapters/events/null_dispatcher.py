from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from camp_match.shared_kernel.domain.identifiers import EntityId


class NullMessageEventDispatcher:
    async def dispatch(self, event_id: EntityId) -> None:
        pass
