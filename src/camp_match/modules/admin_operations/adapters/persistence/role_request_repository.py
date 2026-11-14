from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update

from camp_match.modules.admin_operations.adapters.persistence.models import (
    AdminRoleGrantRequestModel,
)
from camp_match.modules.admin_operations.domain.entities import RoleGrantRequest
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


def _to_entity(model: AdminRoleGrantRequestModel) -> RoleGrantRequest:
    return RoleGrantRequest(
        id=EntityId(model.id),
        target_identity_id=EntityId(model.target_identity_id),
        role=model.role,
        requested_by=EntityId(model.requested_by),
        reason=model.reason,
        status=model.status,
        decided_by=EntityId(model.decided_by) if model.decided_by else None,
        decided_at=model.decided_at,
        decision_reason=model.decision_reason,
        created_at=model.created_at,
        expires_at=model.expires_at,
    )


class SqlAlchemyRoleGrantRequestRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def add(self, request: RoleGrantRequest) -> None:
        model = AdminRoleGrantRequestModel(
            id=request.id.value,
            target_identity_id=request.target_identity_id.value,
            role=request.role,
            requested_by=request.requested_by.value,
            reason=request.reason,
            status=request.status,
            decided_by=request.decided_by.value if request.decided_by else None,
            decided_at=request.decided_at,
            decision_reason=request.decision_reason,
            created_at=request.created_at,
            expires_at=request.expires_at,
        )
        self.session.add(model)
        await self.session.flush()

    async def get(self, request_id: EntityId) -> RoleGrantRequest | None:
        stmt = select(AdminRoleGrantRequestModel).where(
            AdminRoleGrantRequestModel.id == request_id.value
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def get_pending_duplicate(
        self, target_identity_id: EntityId, role: str
    ) -> RoleGrantRequest | None:
        stmt = select(AdminRoleGrantRequestModel).where(
            AdminRoleGrantRequestModel.target_identity_id
            == target_identity_id.value,
            AdminRoleGrantRequestModel.role == role,
            AdminRoleGrantRequestModel.status == "PENDING",
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def list(
        self, page_request: PageRequest | None = None
    ) -> Page[RoleGrantRequest]:
        stmt = select(AdminRoleGrantRequestModel).order_by(
            AdminRoleGrantRequestModel.created_at.desc()
        )

        count_stmt = select(func.count()).select_from(
            AdminRoleGrantRequestModel
        )
        total_res = await self.session.execute(count_stmt)
        total = int(total_res.scalar_one())

        if page_request:
            offset = (page_request.page - 1) * page_request.page_size
            stmt = stmt.offset(offset).limit(page_request.page_size)
            page = page_request.page
            page_size = page_request.page_size
        else:
            page = 1
            page_size = max(total, 1)

        res = await self.session.execute(stmt)
        models = res.scalars().all()
        items = [_to_entity(m) for m in models]

        return Page(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_decision(
        self,
        request_id: EntityId,
        status: str,
        decided_by: EntityId,
        decided_at: datetime,
        decision_reason: str | None = None,
    ) -> bool:
        stmt = (
            update(AdminRoleGrantRequestModel)
            .where(
                AdminRoleGrantRequestModel.id == request_id.value,
                AdminRoleGrantRequestModel.status == "PENDING",
            )
            .values(
                status=status,
                decided_by=decided_by.value,
                decided_at=decided_at,
                decision_reason=decision_reason,
            )
        )
        res = await self.session.execute(stmt)
        return int(res.rowcount) > 0
