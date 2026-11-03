from __future__ import annotations

from typing import Protocol

from camp_match.modules.security.domain.value_objects import Role
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class RoleRepository(Protocol):
    async def get_assigned_roles(self, identity_id: EntityId) -> frozenset[Role]:
        ...

    async def assign_role(self, identity_id: EntityId, role: Role) -> None:
        ...

    async def revoke_role(self, identity_id: EntityId, role: Role) -> None:
        ...

    async def list_identities_with_role(
        self, role: Role, page_request: PageRequest
    ) -> Page[EntityId]:
        ...


class ProfileProvider(Protocol):
    async def get_profile_type(self, identity_id: EntityId) -> str | None:
        ...
