from __future__ import annotations

import structlog

from camp_match.modules.security.application.ports.outbound import RoleRepository
from camp_match.modules.security.domain.value_objects import Role
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class GetAssignedRolesUseCase:
    def __init__(self, role_repo: RoleRepository) -> None:
        self.role_repo = role_repo

    async def execute(self, identity_id: EntityId) -> frozenset[Role]:
        roles = await self.role_repo.get_assigned_roles(identity_id)
        staff_roles = {Role.ADMIN, Role.OPERATIONS}
        return frozenset(r for r in roles if r in staff_roles)
