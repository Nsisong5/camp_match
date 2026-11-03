from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from camp_match.modules.security.domain.value_objects import (
    AuthorizationDecision,
    Permission,
    Role,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True)
class AuthorizationRequest:
    identity_id: EntityId
    permission: Permission
    resource_owner_id: EntityId | None = None


class AuthorizationService(Protocol):
    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        ...


class AssignStaffRole(Protocol):
    async def execute(
        self, actor_id: EntityId, identity_id: EntityId, role: Role
    ) -> None:
        ...


class RevokeStaffRole(Protocol):
    async def execute(
        self, actor_id: EntityId, identity_id: EntityId, role: Role
    ) -> None:
        ...


class ListStaff(Protocol):
    async def execute(
        self, actor_id: EntityId, role: Role, page_request: PageRequest
    ) -> Page[EntityId]:
        ...


class GetAssignedRoles(Protocol):
    async def execute(self, identity_id: EntityId) -> frozenset[Role]:
        ...
