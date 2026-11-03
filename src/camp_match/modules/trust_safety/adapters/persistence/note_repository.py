"""SQLAlchemy Note Repository adapter."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from camp_match.modules.trust_safety.adapters.persistence.models import SafetyNoteModel
from camp_match.modules.trust_safety.domain.entities import InvestigationNote
from camp_match.modules.trust_safety.domain.value_objects import NoteKind
from camp_match.shared_kernel.domain.identifiers import EntityId


def _to_domain(m: SafetyNoteModel) -> InvestigationNote:
    return InvestigationNote(
        id=EntityId(m.id),
        case_id=EntityId(m.case_id),
        author_id=EntityId(m.author_id),
        kind=NoteKind(m.kind),
        content=m.content,
        cited_evidence_ids=tuple(EntityId(eid) for eid in (m.cited_evidence_ids or [])),
        corrects_note_id=EntityId(m.corrects_note_id) if m.corrects_note_id else None,
        created_at=m.created_at,
    )


class SqlAlchemyNoteRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def add(self, note: InvestigationNote) -> None:
        model = SafetyNoteModel(
            id=note.id.value,
            case_id=note.case_id.value,
            author_id=note.author_id.value,
            kind=note.kind.value,
            content=note.content,
            cited_evidence_ids=[str(eid.value) for eid in note.cited_evidence_ids],
            corrects_note_id=note.corrects_note_id.value if note.corrects_note_id else None,
            created_at=note.created_at,
        )
        self.session.add(model)
        await self.session.flush()

    async def list_by_case_id(self, case_id: EntityId) -> list[InvestigationNote]:
        stmt = (
            select(SafetyNoteModel)
            .where(SafetyNoteModel.case_id == case_id.value)
            .order_by(SafetyNoteModel.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return [_to_domain(m) for m in res.scalars().all()]
