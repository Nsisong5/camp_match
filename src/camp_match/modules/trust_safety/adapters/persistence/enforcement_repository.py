"""SQLAlchemy Enforcement Repository adapter."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update

from camp_match.modules.trust_safety.adapters.persistence.models import SafetyEnforcementActionModel
from camp_match.modules.trust_safety.domain.entities import EnforcementAction
from camp_match.modules.trust_safety.domain.value_objects import (
    EnforcementStatus,
    EnforcementType,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


def _to_domain(m: SafetyEnforcementActionModel) -> EnforcementAction:
    return EnforcementAction(
        id=EntityId(m.id),
        case_id=EntityId(m.case_id),
        decision_id=EntityId(m.decision_id),
        action_type=EnforcementType(m.action_type),
        target_user_id=EntityId(m.target_user_id) if m.target_user_id else None,
        target_listing_id=EntityId(m.target_listing_id) if m.target_listing_id else None,
        target_key=m.target_key,
        ends_at=m.ends_at,
        status=EnforcementStatus(m.status),
        rationale=m.rationale,
        proposed_by=EntityId(m.proposed_by),
        proposed_at=m.proposed_at,
        approved_by=EntityId(m.approved_by) if m.approved_by else None,
        approved_at=m.approved_at,
        rejected_reason=m.rejected_reason,
        attempts=m.attempts,
        next_attempt_at=m.next_attempt_at,
        last_error=m.last_error,
        applied_at=m.applied_at,
        reversed_by=EntityId(m.reversed_by) if m.reversed_by else None,
        reversal_reason=m.reversal_reason,
        reversed_at=m.reversed_at,
    )


class SqlAlchemyEnforcementRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def add(self, action: EnforcementAction) -> None:
        model = SafetyEnforcementActionModel(
            id=action.id.value,
            case_id=action.case_id.value,
            decision_id=action.decision_id.value,
            action_type=action.action_type.value,
            target_user_id=action.target_user_id.value if action.target_user_id else None,
            target_listing_id=action.target_listing_id.value if action.target_listing_id else None,
            target_key=action.target_key,
            ends_at=action.ends_at,
            status=action.status.value,
            rationale=action.rationale,
            proposed_by=action.proposed_by.value,
            proposed_at=action.proposed_at,
            approved_by=action.approved_by.value if action.approved_by else None,
            approved_at=action.approved_at,
            rejected_reason=action.rejected_reason,
            attempts=action.attempts,
            next_attempt_at=action.next_attempt_at,
            last_error=action.last_error,
            applied_at=action.applied_at,
            reversed_by=action.reversed_by.value if action.reversed_by else None,
            reversal_reason=action.reversal_reason,
            reversed_at=action.reversed_at,
        )
        self.session.add(model)
        await self.session.flush()

    async def get_by_id(self, action_id: EntityId) -> EnforcementAction | None:
        res = await self.session.get(SafetyEnforcementActionModel, action_id.value)
        return _to_domain(res) if res else None

    async def update(self, action: EnforcementAction, expected_status: EnforcementStatus) -> bool:
        stmt = (
            update(SafetyEnforcementActionModel)
            .where(
                SafetyEnforcementActionModel.id == action.id.value,
                SafetyEnforcementActionModel.status == expected_status.value,
            )
            .values(
                status=action.status.value,
                approved_by=action.approved_by.value if action.approved_by else None,
                approved_at=action.approved_at,
                rejected_reason=action.rejected_reason,
                attempts=action.attempts,
                next_attempt_at=action.next_attempt_at,
                last_error=action.last_error,
                applied_at=action.applied_at,
                reversed_by=action.reversed_by.value if action.reversed_by else None,
                reversal_reason=action.reversal_reason,
                reversed_at=action.reversed_at,
            )
        )
        res = await self.session.execute(stmt)
        return res.rowcount == 1

    async def claim_for_attempt(self, action_id: EntityId, next_attempt_at: datetime) -> EnforcementAction | None:
        if not self.session.in_transaction():
            raise RuntimeError("EnforcementRepository.claim_for_attempt must run within a transaction.")
        
        stmt = (
            select(SafetyEnforcementActionModel)
            .where(
                SafetyEnforcementActionModel.id == action_id.value,
                SafetyEnforcementActionModel.status.in_(["APPROVED", "REVERSAL_PENDING"]),
            )
            .with_for_update(skip_locked=True)
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        if not model:
            return None
        
        model.next_attempt_at = next_attempt_at
        model.attempts += 1
        await self.session.flush()
        return _to_domain(model)

    async def list_due(self, now: datetime, limit: int) -> list[EnforcementAction]:
        stmt = (
            select(SafetyEnforcementActionModel)
            .where(
                SafetyEnforcementActionModel.status.in_(["APPROVED", "REVERSAL_PENDING"]),
                SafetyEnforcementActionModel.next_attempt_at <= now,
            )
            .order_by(SafetyEnforcementActionModel.next_attempt_at.asc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return [_to_domain(m) for m in res.scalars().all()]

    async def list_by_case_id(self, case_id: EntityId) -> list[EnforcementAction]:
        stmt = (
            select(SafetyEnforcementActionModel)
            .where(SafetyEnforcementActionModel.case_id == case_id.value)
            .order_by(SafetyEnforcementActionModel.proposed_at.asc())
        )
        res = await self.session.execute(stmt)
        return [_to_domain(m) for m in res.scalars().all()]

    async def count_enforcement_awaiting_approval(self) -> int:
        stmt = select(func.count(SafetyEnforcementActionModel.id)).where(
            SafetyEnforcementActionModel.status == EnforcementStatus.PROPOSED.value
        )
        res = await self.session.execute(stmt)
        return res.scalar_one()

    async def count_enforcement_retrying(self) -> int:
        stmt = select(func.count(SafetyEnforcementActionModel.id)).where(
            SafetyEnforcementActionModel.status == EnforcementStatus.APPROVED.value,
            SafetyEnforcementActionModel.attempts > 0,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one()

    async def count_enforcement_failed(self) -> int:
        stmt = select(func.count(SafetyEnforcementActionModel.id)).where(
            SafetyEnforcementActionModel.status.in_([
                EnforcementStatus.FAILED.value,
                EnforcementStatus.REVERSAL_FAILED.value,
            ])
        )
        res = await self.session.execute(stmt)
        return res.scalar_one()
