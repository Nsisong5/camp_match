"""Trust & Safety API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from camp_match.modules.trust_safety.domain.value_objects import (
    CasePriority,
    CaseStatus,
    DecisionType,
    EnforcementType,
    NoteKind,
    ReportCategory,
    ReportStatus,
    SubjectType,
)

T = TypeVar("T")


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListingSubjectInput(BaseSchema):
    type: Literal["LISTING"]
    id: UUID


class BookingSubjectInput(BaseSchema):
    type: Literal["BOOKING"]
    id: UUID


class ConversationSubjectInput(BaseSchema):
    type: Literal["CONVERSATION"]
    id: UUID
    message_ids: list[UUID] = Field(..., min_length=1)


ReportSubjectInput = ListingSubjectInput | BookingSubjectInput | ConversationSubjectInput


class ReportCreateRequest(BaseSchema):
    idempotency_key: str = Field(..., min_length=1, max_length=64)
    category: ReportCategory
    description: str = Field(..., min_length=10, max_length=2000)
    subject: ReportSubjectInput


class ReportAckResponse(BaseSchema):
    report_id: UUID
    status: ReportStatus
    created_at: datetime
    replayed: bool


class ReporterReportResponse(BaseSchema):
    id: UUID
    category: ReportCategory
    subject_type: SubjectType
    subject_id: UUID
    description: str
    status: str
    created_at: datetime


class LinkReportSchema(BaseSchema):
    report_id: UUID


class TriageCaseSchema(BaseSchema):
    priority: CasePriority
    reason: str | None = None


class AssignCaseSchema(BaseSchema):
    assignee_id: UUID | None = None


class ChangeCaseStatusSchema(BaseSchema):
    to_status: CaseStatus
    reason: str | None = None


class AddNoteSchema(BaseSchema):
    kind: NoteKind
    content: str = Field(..., min_length=1, max_length=2000)
    cited_evidence_ids: list[UUID] = Field(default_factory=list)
    corrects_note_id: UUID | None = None


class RecordDecisionSchema(BaseSchema):
    decision_type: DecisionType
    rationale: str = Field(..., min_length=10, max_length=2000)
    cited_evidence_ids: list[UUID] = Field(default_factory=list)
    cited_note_ids: list[UUID] = Field(default_factory=list)


class ProposeEnforcementSchema(BaseSchema):
    decision_id: UUID
    action_type: EnforcementType
    target_user_id: UUID | None = None
    target_listing_id: UUID | None = None
    ends_at: datetime | None = None
    rationale: str = Field(..., min_length=10, max_length=2000)


class RejectEnforcementSchema(BaseSchema):
    reason: str = Field(..., min_length=5, max_length=500)


class ReverseEnforcementSchema(BaseSchema):
    reason: str = Field(..., min_length=5, max_length=500)


class PageSchema[T](BaseSchema):
    items: list[T]
    total: int
    page: int
    page_size: int
