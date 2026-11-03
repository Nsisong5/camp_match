"""SQLAlchemy Decision Repository adapter."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from camp_match.modules.trust_safety.adapters.persistence.models import SafetyDecisionModel
from camp_match.modules.trust_safety.domain.entities import CaseDecision
from camp_match.modules.trust_safety.domain.value_objects import DecisionType
from camp_match.shared_kernel.domain.identifiers import EntityId


def _to_domain(m: SafetyDecisionModel) -> CaseDecision:
    return CaseDecision(
        id=EntityId(m.id),
        case_id=EntityId(m.case_id),
        cycle=m.cycle,
        decision_type=DecisionType(m.decision_type),
        rationale=m.rationale,
        cited_evidence_ids=tuple(EntityId(eid) for eid in (m.cited_evidence_ids or [])),
        cited_note_ids=tuple(EntityId(nid) for nid in (m.cited_note_ids or [])),
        decided_by=EntityId(m.decided_by),
        decided_at=m.decided_at,
    )


class SqlAlchemyDecisionRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def add(self, decision: CaseDecision) -> None:
        model = SafetyDecisionModel(
            id=decision.id.value,
            case_id=decision.case_id.value,
            cycle=decision.cycle,
            decision_type=decision.decision_type.value,
            is_final=decision.is_final,
            rationale=decision.rationale,
            cited_evidence_ids=[str(eid.value) for eid in decision.cited_evidence_ids],
            cited_note_ids=[str(nid.value) for nid in decision.cited_note_ids],
            decided_by=decision.decided_by.value,
            decided_at=decision.decided_at,
        )
        self.session.add(model)
        await self.session.flush()

    async def list_by_case_id(self, case_id: EntityId) -> list[CaseDecision]:
        stmt = (
            select(SafetyDecisionModel)
            .where(SafetyDecisionModel.case_id == case_id.value)
            .order_by(SafetyDecisionModel.decided_at.asc())
        )
        res = await self.session.execute(stmt)
        return [_to_domain(m) for m in res.scalars().all()]
