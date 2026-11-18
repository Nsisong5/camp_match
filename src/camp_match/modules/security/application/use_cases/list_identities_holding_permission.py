from __future__ import annotations

import structlog

from camp_match.modules.security.application.ports.outbound import RoleRepository
from camp_match.modules.security.domain.policy import permissions_for
from camp_match.modules.security.domain.value_objects import Permission, Role
from camp_match.shared_kernel.application.pagination import PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class ListIdentitiesHoldingPermissionUseCase:
    def __init__(self, role_repo: RoleRepository) -> None:
        self.role_repo = role_repo

    async def execute(self, permission: Permission) -> list[EntityId]:
        granting_roles = [r for r in Role if permission in permissions_for(r)]
        seen: set[EntityId] = set()
        result: list[EntityId] = []

        for role in granting_roles:
            page = 1
            page_size = 100
            while True:
                page_result = await self.role_repo.list_identities_with_role(
                    role, PageRequest(page=page, page_size=page_size)
                )
                for identity_id in page_result.items:
                    if identity_id not in seen:
                        seen.add(identity_id)
                        result.append(identity_id)
                if len(page_result.items) < page_size or page * page_size >= page_result.total:
                    break
                page += 1

        return result
