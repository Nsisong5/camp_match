from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.modules.security.adapters.persistence.models import SecurityUserRoleModel
from camp_match.modules.security.application.ports.outbound import RoleRepository
from camp_match.modules.security.domain.value_objects import Role
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class SqlAlchemyRoleRepository(RoleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_assigned_roles(self, identity_id: EntityId) -> frozenset[Role]:
        stmt = select(SecurityUserRoleModel.role).where(
            SecurityUserRoleModel.identity_id == identity_id.value
        )
        result = await self._session.execute(stmt)
        roles = result.scalars().all()
        return frozenset(Role[role] for role in roles)


    async def assign_role(self, identity_id: EntityId, role: Role) -> None:
        model = SecurityUserRoleModel(
            id=uuid.uuid4(), identity_id=identity_id.value, role=role.name
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError:
            # Idempotent: ignore if role already exists
            await self._session.rollback()

    async def revoke_role(self, identity_id: EntityId, role: Role) -> None:
        stmt = delete(SecurityUserRoleModel).where(
            SecurityUserRoleModel.identity_id == identity_id.value,
            SecurityUserRoleModel.role == role.name,
        )
        await self._session.execute(stmt)
        # Idempotent: no error if role didn't exist

    async def list_identities_with_role(
        self, role: Role, page_request: PageRequest
    ) -> Page[EntityId]:
        count_stmt = select(func.count()).select_from(SecurityUserRoleModel).where(
            SecurityUserRoleModel.role == role.name
        )
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = (
            select(SecurityUserRoleModel.identity_id)
            .where(SecurityUserRoleModel.role == role.name)
            .offset((page_request.page - 1) * page_request.page_size)
            .limit(page_request.page_size)
        )
        result = await self._session.execute(stmt)
        identity_ids = [EntityId(row[0]) for row in result.all()]
        return Page(
            items=identity_ids,
            total=total,
            page=page_request.page,
            page_size=page_request.page_size,
        )
