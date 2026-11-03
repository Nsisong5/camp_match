from __future__ import annotations

from camp_match.modules.security.application.use_cases.authorize_action import (
    AuthorizeActionUseCase,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.errors import ForbiddenError
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessAuthorizationService:
    def __init__(self, authorize_use_case: AuthorizeActionUseCase) -> None:
        self._authorize_use_case = authorize_use_case

    async def authorize(
        self,
        caller_id: EntityId,
        permission: Permission,
        resource_owner_id: EntityId | None = None,
    ) -> None:
        decision = await self._authorize_use_case.execute(caller_id, permission, resource_owner_id)
        if decision.outcome.name != "ALLOWED":
            raise ForbiddenError(decision.reason)
