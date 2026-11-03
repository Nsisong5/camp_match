from __future__ import annotations

import structlog

from camp_match.modules.security.application.errors import (
    RoleNotManageable,
    SecurityForbiddenError,
)
from camp_match.modules.security.application.ports.inbound import (
    AuthorizationRequest,
    AuthorizationService,
)
from camp_match.modules.security.application.ports.outbound import RoleRepository
from camp_match.modules.security.domain.value_objects import Permission, Role
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class AssignStaffRoleUseCase:
    def __init__(
        self,
        role_repo: RoleRepository,
        authorization_service: AuthorizationService,
        uow: UnitOfWork,
    ) -> None:
        self.role_repo = role_repo
        self.authorization_service = authorization_service
        self.uow = uow

    async def execute(self, actor_id: EntityId, identity_id: EntityId, role: Role) -> None:
        auth_decision = await self.authorization_service.authorize(
            AuthorizationRequest(
                identity_id=actor_id, permission=Permission.ADMIN_STAFF_MANAGE
            )
        )
        if auth_decision.outcome.name != "ALLOWED":
            raise SecurityForbiddenError("Action requires ADMIN_STAFF_MANAGE permission.")

        if role != Role.OPERATIONS:
            raise RoleNotManageable("Only the OPERATIONS role is manageable via staff API.")

        async with self.uow:
            await self.role_repo.assign_role(identity_id, role)
            await self.uow.commit()
