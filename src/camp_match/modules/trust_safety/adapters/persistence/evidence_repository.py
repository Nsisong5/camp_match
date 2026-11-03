"""SQLAlchemy Evidence Repository adapter."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from camp_match.modules.trust_safety.adapters.persistence.models import SafetyEvidenceModel
from camp_match.modules.trust_safety.domain.entities import EvidenceItem
from camp_match.modules.trust_safety.domain.value_objects import (
    Confidentiality,
    EvidenceType,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


def _to_domain(m: SafetyEvidenceModel) -> EvidenceItem:
    return EvidenceItem(
        id=EntityId(m.id),
        report_id=EntityId(m.report_id),
        evidence_type=EvidenceType(m.evidence_type),
        resource_type=m.resource_type,
        resource_id=EntityId(m.resource_id),
        conversation_id=EntityId(m.conversation_id) if m.conversation_id else None,
        snapshot=m.snapshot,
        content_sha256=m.content_sha256,
        collected_by=EntityId(m.collected_by),
        collected_at=m.collected_at,
        source=m.source,
        confidentiality=Confidentiality(m.confidentiality),
    )


class SqlAlchemyEvidenceRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def add(self, evidence: EvidenceItem) -> None:
        model = SafetyEvidenceModel(
            id=evidence.id.value,
            report_id=evidence.report_id.value,
            evidence_type=evidence.evidence_type.value,
            resource_type=evidence.resource_type,
            resource_id=evidence.resource_id.value,
            conversation_id=evidence.conversation_id.value if evidence.conversation_id else None,
            snapshot=evidence.snapshot,
            content_sha256=evidence.content_sha256,
            collected_by=evidence.collected_by.value,
            collected_at=evidence.collected_at,
            source=evidence.source,
            confidentiality=evidence.confidentiality.value,
        )
        self.session.add(model)
        await self.session.flush()

    async def get_by_id(self, evidence_id: EntityId) -> EvidenceItem | None:
        res = await self.session.get(SafetyEvidenceModel, evidence_id.value)
        return _to_domain(res) if res else None

    async def list_by_case_id(self, case_id: EntityId) -> list[EvidenceItem]:
        # Evidence is linked via report_id. We can join or query reports linked to case.
        from camp_match.modules.trust_safety.adapters.persistence.models import SafetyCaseReportModel
        stmt = (
            select(SafetyEvidenceModel)
            .join(SafetyCaseReportModel, SafetyCaseReportModel.report_id == SafetyEvidenceModel.report_id)
            .where(SafetyCaseReportModel.case_id == case_id.value)
            .order_by(SafetyEvidenceModel.collected_at.asc())
        )
        res = await self.session.execute(stmt)
        return [_to_domain(m) for m in res.scalars().all()]

    async def list_by_report_id(self, report_id: EntityId) -> list[EvidenceItem]:
        stmt = (
            select(SafetyEvidenceModel)
            .where(SafetyEvidenceModel.report_id == report_id.value)
            .order_by(SafetyEvidenceModel.collected_at.asc())
        )
        res = await self.session.execute(stmt)
        return [_to_domain(m) for m in res.scalars().all()]
