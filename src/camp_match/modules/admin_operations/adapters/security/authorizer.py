from __future__ import annotations

from typing import Any

from camp_match.modules.admin_operations.application.ports.outbound import Authorizer
from camp_match.modules.security.application.ports.inbound import AuthorizationRequest
from camp_match.modules.security.domain.value_objects import (
    AuthorizationOutcome,
    Permission,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessAuthorizer(Authorizer):
    def __init__(self, auth_service: Any) -> None:
        self._auth = auth_service

    async def authorize(self, identity_id: EntityId, permission: Any) -> bool:
        perm = (
            permission
            if isinstance(permission, Permission)
            else Permission(permission)
        )
        decision = await self._auth.execute(
            AuthorizationRequest(identity_id=identity_id, permission=perm)
        )
        if decision.outcome == AuthorizationOutcome.ALLOWED:
            return True
        from camp_match.modules.security.application.errors import (
            SecurityForbiddenError,
        )

        raise SecurityForbiddenError("Action not permitted.")
