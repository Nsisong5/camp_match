from __future__ import annotations

from typing import Any

from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class PaymentSourceAdapter:
    def __init__(self, dispute_repo: Any, authorizer: Any) -> None:
        self._dispute_repo = dispute_repo
        self._authorizer = authorizer

    async def fetch(self, actor_id: EntityId) -> dict[str, Any]:
        await self._authorizer.authorize(actor_id, Permission.PAYMENT_REVIEW)
        count = await self._dispute_repo.count_pending()
        return {"pending_disputes": count}
