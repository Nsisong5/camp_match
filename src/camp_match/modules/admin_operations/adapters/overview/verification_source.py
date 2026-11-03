from __future__ import annotations

from typing import Any

from camp_match.modules.verification.application.ports.inbound import (
    ListPendingReviewsRequest,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


class VerificationSourceAdapter:
    def __init__(self, list_pending_reviews_uc: Any) -> None:
        self._uc = list_pending_reviews_uc

    async def fetch(self, actor_id: EntityId) -> dict[str, Any]:
        items = await self._uc.execute(
            ListPendingReviewsRequest(caller_id=actor_id)
        )
        return {"pending_reviews": len(items) if items else 0}
