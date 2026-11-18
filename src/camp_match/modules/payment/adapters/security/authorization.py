from __future__ import annotations

from typing import Any

from camp_match.modules.security.application.ports.inbound import AuthorizationRequest
from camp_match.modules.security.application.use_cases.authorize_action import (
    AuthorizeActionUseCase,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.errors import ForbiddenError
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessAuthorizationService:
    def __init__(self, authorize_use_case: AuthorizeActionUseCase) -> None:
        self._authorize_use_case = authorize_use_case

    @property
    def authorizer(self) -> Any:
        # Return self so that use cases calling .authorizer.execute(...) work
        return self

    async def execute(
        self,
        identity_id: EntityId,
        permission: Permission,
        resource_owner_id: EntityId | None = None,
    ) -> Any:
        # Map to the signature expected by Payment use cases
        return await self.authorize(identity_id, permission, resource_owner_id)

    async def authorize(
        self,
        caller_id: EntityId,
        permission: Permission,
        resource_owner_id: EntityId | None = None,
    ) -> None:
        decision = await self._authorize_use_case.execute(
            AuthorizationRequest(
                identity_id=caller_id,
                permission=permission,
                resource_owner_id=resource_owner_id,
            )
        )
        if decision.outcome.name != "ALLOWED":
            raise ForbiddenError(decision.reason)
