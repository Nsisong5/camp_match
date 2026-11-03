"""Record decision use case for Trust & Safety (Chunk 12)."""
from __future__ import annotations

from typing import Any

from camp_match.modules.trust_safety.application.errors import CaseNotFound, InvalidDecision
from camp_match.modules.trust_safety.application.ports.inbound import RecordDecisionRequest
from camp_match.modules.trust_safety.application.ports.outbound import (
    CaseRepository,
    DecisionRepository,
    EvidenceRepository,
    NoteRepository,
)
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.modules.trust_safety.domain.entities import CaseDecision
from camp_match.modules.trust_safety.domain.value_objects import CaseStatus, DecisionType, NoteKind
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId


class RecordDecisionUseCase:
    def __init__(
        self,
        case_repo: CaseRepository,
        decision_repo: DecisionRepository,
        evidence_repo: EvidenceRepository,
        note_repo: NoteRepository,
        case_access: CaseAccess,
        unit_of_work: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._case_repo = case_repo
        self._decision_repo = decision_repo
        self._evidence_repo = evidence_repo
        self._note_repo = note_repo
        self._case_access = case_access
        self._uow = unit_of_work
        self._clock = clock

    async def execute(self, request: RecordDecisionRequest) -> EntityId:
        case = await self._case_repo.get_by_id(request.case_id)
        if not case:
            raise CaseNotFound("Case not found.")

        if case.status == CaseStatus.ESCALATED:
            await self._case_access.require_approver(request.actor_id, request.case_id)
        else:
            await self._case_access.require_reviewer(request.actor_id, request.case_id)

        if case.status not in (CaseStatus.IN_REVIEW, CaseStatus.ESCALATED):
            raise InvalidDecision(f"Cannot record decision for case in status {case.status}.")

        if not (10 <= len(request.rationale) <= 2000):
            raise InvalidDecision("Rationale length must be between 10 and 2000 characters.")

        existing_decisions = await self._decision_repo.list_by_case_id(request.case_id)
        cycle_decisions = [d for d in existing_decisions if d.cycle == case.cycle]
        
        is_new_final = request.decision_type != DecisionType.FURTHER_INVESTIGATION_REQUIRED
        if is_new_final and any(d.is_final for d in cycle_decisions):
            raise InvalidDecision("A final decision already exists for this case cycle.")

        case_evidence = {e.id for e in await self._evidence_repo.list_by_case_id(request.case_id)}
        for eid in request.cited_evidence_ids:
            if eid not in case_evidence:
                raise InvalidDecision("Cited evidence does not belong to the case.")

        notes = await self._note_repo.list_by_case_id(request.case_id)
        case_notes = {n.id for n in notes}
        note_map = {n.id: n for n in notes}
        for nid in request.cited_note_ids:
            if nid not in case_notes:
                raise InvalidDecision("Cited note does not belong to the case.")

        if request.decision_type == DecisionType.VIOLATION_ESTABLISHED:
            if not request.cited_note_ids:
                raise InvalidDecision("VIOLATION_ESTABLISHED decision requires at least one cited note.")
            for nid in request.cited_note_ids:
                note = note_map.get(nid)
                if not note or note.kind != NoteKind.CORROBORATED_FACT:
                    raise InvalidDecision("All cited notes for VIOLATION_ESTABLISHED must be CORROBORATED_FACT.")

        now = self._clock.now()
        decision_id = EntityId.new()
        decision = CaseDecision(
            id=decision_id,
            case_id=request.case_id,
            cycle=case.cycle,
            decision_type=request.decision_type,
            rationale=request.rationale,
            cited_evidence_ids=request.cited_evidence_ids,
            cited_note_ids=request.cited_note_ids,
            decided_by=request.actor_id,
            decided_at=now,
        )

        async with self._uow:
            try:
                await self._decision_repo.add(decision)
                await self._case_repo.add_event(
                    case_id=request.case_id,
                    report_id=None,
                    event_type="DECISION_RECORDED",
                    actor_id=request.actor_id,
                    details={"decision_id": str(decision_id), "decision_type": request.decision_type.value},
                )
                await self._uow.commit()
            except Exception as e:
                await self._uow.rollback()
                raise InvalidDecision("Failed to record decision due to conflict or error.") from e

        return decision_id
