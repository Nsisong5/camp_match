from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.messaging.application.ports.outbound import RestrictionDecision
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from camp_match.modules.identity.adapters.persistence.repository import (
        SqlAlchemyIdentityRepository,
    )
    from camp_match.modules.messaging.adapters.persistence.repository import (
        SqlAlchemyRestrictionRepository,
    )


class IdentityBackedRestrictionProvider:
    def __init__(
        self,
        account_repo: SqlAlchemyIdentityRepository,
        restriction_repo: SqlAlchemyRestrictionRepository,
    ) -> None:
        self._account_repo = account_repo
        self._restriction_repo = restriction_repo

    async def check(self, actor_id: EntityId, counterpart_id: EntityId | None = None) -> RestrictionDecision:
        actor = await self._account_repo.get_by_id(actor_id)
        if not actor or actor.status.name != "ACTIVE":
            return RestrictionDecision(allowed=False, reason="Actor account is not active.")

        if counterpart_id is not None:
            counterpart = await self._account_repo.get_by_id(counterpart_id)
            if not counterpart or counterpart.status.name != "ACTIVE":
                return RestrictionDecision(allowed=False, reason="Counterpart account is not active.")

            active_restriction = await self._restriction_repo.get_active_for_user(actor_id)
            if active_restriction:
                return RestrictionDecision(allowed=False, reason="Communication is restricted.")

        return RestrictionDecision(allowed=True)
