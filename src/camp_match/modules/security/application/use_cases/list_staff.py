from __future__ import annotations

import structlog

from camp_match.modules.security.application.errors import SecurityForbiddenError
from camp_match.modules.security.application.ports.inbound import (
    AuthorizationRequest,
    AuthorizationService,
)
from camp_match.modules.security.application.ports.outbound import RoleRepository
from camp_match.modules.security.domain.value_objects import Permission, Role
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class ListStaffUseCase:
    def __init__(
        self,
        role_repo: RoleRepository,
        authorization_service: AuthorizationService,
    ) -> None:
        self.role_repo = role_repo
        self.authorization_service = authorization_service

    async def execute(
        self, actor_id: EntityId, role: Role, page_request: PageRequest
    ) -> Page[EntityId]:
        auth_decision = await self.authorization_service.authorize(
            AuthorizationRequest(
                identity_id=actor_id, permission=Permission.ADMIN_STAFF_MANAGE
            )
        )
        if auth_decision.outcome.name != "ALLOWED":
            raise SecurityForbiddenError("Action requires ADMIN_STAFF_MANAGE permission.")

        return await self.role_repo.list_identities_with_role(role, page_request)
