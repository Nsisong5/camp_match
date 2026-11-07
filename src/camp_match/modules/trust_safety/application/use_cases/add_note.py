"""Add note use case for Trust & Safety."""
from __future__ import annotations

from typing import Any

from camp_match.modules.trust_safety.application.errors import InvalidNote, NoteNotFound
from camp_match.modules.trust_safety.application.ports.inbound import AddNoteRequest
from camp_match.modules.trust_safety.application.ports.outbound import (
    CaseRepository,
    EvidenceRepository,
    NoteRepository,
)
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.modules.trust_safety.domain.entities import InvestigationNote
from camp_match.modules.trust_safety.domain.value_objects import CaseStatus, NoteKind
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId


class AddNoteUseCase:
    def __init__(
        self,
        case_repo: CaseRepository,
        note_repo: NoteRepository,
        evidence_repo: EvidenceRepository,
        case_access: CaseAccess,
        unit_of_work: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._case_repo = case_repo
        self._note_repo = note_repo
        self._evidence_repo = evidence_repo
        self._case_access = case_access
        self._uow = unit_of_work
        self._clock = clock

    async def execute(self, request: AddNoteRequest) -> EntityId:
        case = await self._case_access.require_reviewer(request.actor_id, request.case_id)

        if case.status == CaseStatus.CLOSED:
            raise InvalidNote("Cannot add note to a closed case.")

        if not (1 <= len(request.content) <= 2000):
            raise InvalidNote("Note content length must be between 1 and 2000 characters.")

        if request.kind == NoteKind.CORROBORATED_FACT and not request.cited_evidence_ids:
            raise InvalidNote("CORROBORATED_FACT notes must cite at least one evidence item.")

        if request.corrects_note_id:
            target_note = await self._note_repo.get_by_id(request.corrects_note_id)
            if not target_note:
                raise NoteNotFound("Note to correct not found.")

        now = self._clock.now()
        note_id = EntityId.new()
        note = InvestigationNote(
            id=note_id,
            case_id=request.case_id,
            author_id=request.actor_id,
            kind=request.kind,
            content=request.content,
            cited_evidence_ids=request.cited_evidence_ids,
            corrects_note_id=request.corrects_note_id,
            created_at=now,
        )

        async with self._uow:
            await self._note_repo.add(note)
            await self._case_repo.add_event(
                case_id=request.case_id,
                report_id=None,
                event_type="NOTE_ADDED",
                actor_id=request.actor_id,
                details={"note_id": str(note_id), "kind": request.kind.value},
            )
            await self._uow.commit()

        return note_id
