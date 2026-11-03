from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True)
class SafetyRecoveryRequest:
    actor_id: EntityId
    enforcement_id: EntityId


class InProcessSafetyRecovery:
    def __init__(self, requeue_failed_uc: Any) -> None:
        self._uc = requeue_failed_uc

    async def requeue_failed(
        self, actor_id: EntityId, enforcement_id: EntityId
    ) -> int:
        await self._uc.execute(
            SafetyRecoveryRequest(actor_id=actor_id, enforcement_id=enforcement_id)
        )
        return 1
