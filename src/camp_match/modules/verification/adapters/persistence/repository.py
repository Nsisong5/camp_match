from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import desc, select, update

from camp_match.modules.verification.adapters.persistence.models import (
    InspectionModel,
    InspectionObservationModel,
    VerificationCaseModel,
    VerificationDecisionModel,
    VerificationEvidenceModel,
    VerificationHistoryModel,
)
from camp_match.modules.verification.domain.entities import (
    Evidence,
    Inspection,
    InspectionObservation,
    VerificationCase,
    VerificationDecision,
)
from camp_match.modules.verification.domain.value_objects import (
    ChecklistItem,
    DecisionOutcome,
    EvidenceReviewStatus,
    EvidenceType,
    InspectionResult,
    InspectionStatus,
    VerificationStatus,
    VerificationTargetType,
)
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyVerificationCaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, case: VerificationCase) -> None:
        model = VerificationCaseModel(
            id=case.id.value,
            target_type=case.target_type.value,
            target_id=case.target_id.value,
            status=case.status.value,
            previous_case_id=case.previous_case_id.value if case.previous_case_id else None,
            submitted_by=case.submitted_by.value,
            expires_at=case.expires_at,
            revoked_at=case.revoked_at,
            revoked_by=case.revoked_by.value if case.revoked_by else None,
            revocation_reason=case.revocation_reason,
        )
        self._session.add(model)

    async def get_by_id(self, case_id: EntityId) -> VerificationCase | None:
        stmt = select(VerificationCaseModel).where(VerificationCaseModel.id == case_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_latest_by_target(
        self, target_type: VerificationTargetType, target_id: EntityId
    ) -> VerificationCase | None:
        stmt = (
            select(VerificationCaseModel)
            .where(
                VerificationCaseModel.target_type == target_type.value,
                VerificationCaseModel.target_id == target_id.value,
            )
            .order_by(desc(VerificationCaseModel.created_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_by_submitter(self, submitter_id: EntityId) -> list[VerificationCase]:
        stmt = (
            select(VerificationCaseModel)
            .where(VerificationCaseModel.submitted_by == submitter_id.value)
            .order_by(desc(VerificationCaseModel.created_at))
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def list_pending_review(self) -> list[VerificationCase]:
        stmt = (
            select(VerificationCaseModel)
            .where(
                VerificationCaseModel.status.in_([
                    VerificationStatus.SUBMITTED.value,
                    VerificationStatus.UNDER_REVIEW.value,
                    VerificationStatus.DECISION_PENDING.value,
                ])
            )
            .order_by(VerificationCaseModel.created_at)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def update(self, case: VerificationCase) -> None:
        stmt = (
            update(VerificationCaseModel)
            .where(VerificationCaseModel.id == case.id.value)
            .values(
                status=case.status.value,
                expires_at=case.expires_at,
                revoked_at=case.revoked_at,
                revoked_by=case.revoked_by.value if case.revoked_by else None,
                revocation_reason=case.revocation_reason,
            )
        )
        await self._session.execute(stmt)

    async def update_status_conditionally(
        self,
        case_id: EntityId,
        expected_status: VerificationStatus,
        new_status: VerificationStatus,
        expires_at=None,
        revoked_at=None,
        revoked_by=None,
        revocation_reason=None,
    ) -> bool:
        values = {"status": new_status.value}
        if expires_at is not None:
            values["expires_at"] = expires_at
        if revoked_at is not None:
            values["revoked_at"] = revoked_at
        if revoked_by is not None:
            values["revoked_by"] = revoked_by.value
        if revocation_reason is not None:
            values["revocation_reason"] = revocation_reason

        stmt = (
            update(VerificationCaseModel)
            .where(
                VerificationCaseModel.id == case_id.value,
                VerificationCaseModel.status == expected_status.value,
            )
            .values(**values)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    def _to_domain(self, model: VerificationCaseModel) -> VerificationCase:
        return VerificationCase(
            id=EntityId(model.id),
            target_type=VerificationTargetType(model.target_type),
            target_id=EntityId(model.target_id),
            status=VerificationStatus(model.status),
            submitted_by=EntityId(model.submitted_by),
            previous_case_id=EntityId(model.previous_case_id) if model.previous_case_id else None,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
            revoked_by=EntityId(model.revoked_by) if model.revoked_by else None,
            revocation_reason=model.revocation_reason,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class SQLAlchemyEvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, evidence: Evidence) -> None:
        model = VerificationEvidenceModel(
            id=evidence.id.value,
            verification_case_id=evidence.verification_case_id.value,
            evidence_type=evidence.evidence_type.value,
            media_id=evidence.media_id.value,
            submitted_by=evidence.submitted_by.value,
            source_description=evidence.source_description,
            captured_at=evidence.captured_at,
            inspection_id=evidence.inspection_id.value if evidence.inspection_id else None,
            review_status=evidence.review_status.value,
            review_notes=evidence.review_notes,
        )
        self._session.add(model)

    async def get_by_id(self, evidence_id: EntityId) -> Evidence | None:
        stmt = select(VerificationEvidenceModel).where(VerificationEvidenceModel.id == evidence_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_by_case_id(self, case_id: EntityId) -> list[Evidence]:
        stmt = select(VerificationEvidenceModel).where(VerificationEvidenceModel.verification_case_id == case_id.value)
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def update(self, evidence: Evidence) -> None:
        stmt = (
            update(VerificationEvidenceModel)
            .where(VerificationEvidenceModel.id == evidence.id.value)
            .values(
                review_status=evidence.review_status.value,
                review_notes=evidence.review_notes,
            )
        )
        await self._session.execute(stmt)

    def _to_domain(self, model: VerificationEvidenceModel) -> Evidence:
        return Evidence(
            id=EntityId(model.id),
            verification_case_id=EntityId(model.verification_case_id),
            evidence_type=EvidenceType(model.evidence_type),
            media_id=EntityId(model.media_id),
            submitted_by=EntityId(model.submitted_by),
            source_description=model.source_description,
            captured_at=model.captured_at,
            inspection_id=EntityId(model.inspection_id) if model.inspection_id else None,
            review_status=EvidenceReviewStatus(model.review_status),
            review_notes=model.review_notes,
            created_at=model.created_at,
        )


class SQLAlchemyInspectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, inspection: Inspection) -> None:
        model = InspectionModel(
            id=inspection.id.value,
            verification_case_id=inspection.verification_case_id.value,
            inspector_id=inspection.inspector_id.value,
            assigned_by=inspection.assigned_by.value,
            status=inspection.status.value,
            started_at=inspection.started_at,
            completed_at=inspection.completed_at,
            result=inspection.result.value if inspection.result else None,
            notes=inspection.notes,
        )
        self._session.add(model)

    async def get_by_id(self, inspection_id: EntityId) -> Inspection | None:
        stmt = select(InspectionModel).where(InspectionModel.id == inspection_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_active_by_case_id(self, case_id: EntityId) -> Inspection | None:
        stmt = (
            select(InspectionModel)
            .where(
                InspectionModel.verification_case_id == case_id.value,
                InspectionModel.status.in_([InspectionStatus.ASSIGNED.value, InspectionStatus.IN_PROGRESS.value]),
            )
            .order_by(desc(InspectionModel.assigned_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_latest_by_case_id(self, case_id: EntityId) -> Inspection | None:
        stmt = (
            select(InspectionModel)
            .where(InspectionModel.verification_case_id == case_id.value)
            .order_by(desc(InspectionModel.assigned_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_by_inspector(self, inspector_id: EntityId) -> list[Inspection]:
        stmt = select(InspectionModel).where(InspectionModel.inspector_id == inspector_id.value)
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def update(self, inspection: Inspection) -> None:
        stmt = (
            update(InspectionModel)
            .where(InspectionModel.id == inspection.id.value)
            .values(
                status=inspection.status.value,
                started_at=inspection.started_at,
                completed_at=inspection.completed_at,
                result=inspection.result.value if inspection.result else None,
                notes=inspection.notes,
            )
        )
        await self._session.execute(stmt)

    def _to_domain(self, model: InspectionModel) -> Inspection:
        return Inspection(
            id=EntityId(model.id),
            verification_case_id=EntityId(model.verification_case_id),
            inspector_id=EntityId(model.inspector_id),
            assigned_by=EntityId(model.assigned_by),
            status=InspectionStatus(model.status),
            assigned_at=model.assigned_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            result=InspectionResult(model.result) if model.result else None,
            notes=model.notes,
        )


class SQLAlchemyInspectionObservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, observation: InspectionObservation) -> None:
        model = InspectionObservationModel(
            id=observation.id.value,
            inspection_id=observation.inspection_id.value,
            item=observation.item.value,
            passed=observation.passed,
            notes=observation.notes,
        )
        self._session.add(model)

    async def list_by_inspection_id(self, inspection_id: EntityId) -> list[InspectionObservation]:
        stmt = select(InspectionObservationModel).where(InspectionObservationModel.inspection_id == inspection_id.value)
        result = await self._session.execute(stmt)
        return [
            InspectionObservation(
                id=EntityId(m.id),
                inspection_id=EntityId(m.inspection_id),
                item=ChecklistItem(m.item),
                passed=m.passed,
                notes=m.notes,
                created_at=m.created_at,
            )
            for m in result.scalars().all()
        ]


class SQLAlchemyVerificationDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, decision: VerificationDecision) -> None:
        model = VerificationDecisionModel(
            id=decision.id.value,
            verification_case_id=decision.verification_case_id.value,
            outcome=decision.outcome.value,
            reason=decision.reason,
            decided_by=decision.decided_by.value,
            decided_at=decision.decided_at,
        )
        self._session.add(model)

    async def get_by_case_id(self, case_id: EntityId) -> VerificationDecision | None:
        stmt = select(VerificationDecisionModel).where(VerificationDecisionModel.verification_case_id == case_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return VerificationDecision(
            id=EntityId(model.id),
            verification_case_id=EntityId(model.verification_case_id),
            outcome=DecisionOutcome(model.outcome),
            reason=model.reason,
            decided_by=EntityId(model.decided_by),
            decided_at=model.decided_at,
        )


class SQLAlchemyHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, case_id: EntityId, event_type: str, actor_id: EntityId | None, details: str | None) -> None:
        model = VerificationHistoryModel(
            id=EntityId.new().value,
            verification_case_id=case_id.value,
            event_type=event_type,
            actor_id=actor_id.value if actor_id else None,
            details=details,
        )
        self._session.add(model)

    async def list_by_case_id(self, case_id: EntityId) -> list[dict]:
        stmt = (
            select(VerificationHistoryModel)
            .where(VerificationHistoryModel.verification_case_id == case_id.value)
            .order_by(VerificationHistoryModel.occurred_at)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "id": str(m.id),
                "event_type": m.event_type,
                "actor_id": str(m.actor_id) if m.actor_id else None,
                "occurred_at": m.occurred_at.isoformat() if m.occurred_at else None,
                "details": m.details,
            }
            for m in result.scalars().all()
        ]
