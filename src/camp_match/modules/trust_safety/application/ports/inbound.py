"""Trust & Safety inbound ports and DTO views."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from camp_match.modules.trust_safety.domain.value_objects import (
    CasePriority,
    CaseStatus,
    Confidentiality,
    DecisionType,
    EnforcementStatus,
    EnforcementType,
    EvidenceType,
    NoteKind,
    ReportCategory,
    ReportStatus,
    SubjectType,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, slots=True)
class ReporterReportView:
    id: EntityId
    category: ReportCategory
    subject_type: SubjectType
    subject_id: EntityId
    description: str
    status: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReportAck:
    report_id: EntityId
    status: ReportStatus
    created_at: datetime
    replayed: bool


@dataclass(frozen=True, slots=True)
class ReviewerReportView:
    id: EntityId
    reporter_id: EntityId
    category: ReportCategory
    subject_type: SubjectType
    subject_id: EntityId
    description: str
    status: ReportStatus
    case_id: EntityId | None
    similar_report_count: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EvidenceMetadataView:
    id: EntityId
    report_id: EntityId
    evidence_type: EvidenceType
    resource_type: str
    resource_id: EntityId
    collected_by: EntityId
    collected_at: datetime
    source: str
    confidentiality: Confidentiality


@dataclass(frozen=True, slots=True)
class EvidenceContentView(EvidenceMetadataView):
    conversation_id: EntityId | None = None
    snapshot: dict[str, Any] | None = None
    content_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class NoteView:
    id: EntityId
    case_id: EntityId
    author_id: EntityId
    kind: NoteKind
    content: str
    cited_evidence_ids: tuple[EntityId, ...]
    corrects_note_id: EntityId | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DecisionView:
    id: EntityId
    case_id: EntityId
    cycle: int
    decision_type: DecisionType
    is_final: bool
    rationale: str
    cited_evidence_ids: tuple[EntityId, ...]
    cited_note_ids: tuple[EntityId, ...]
    decided_by: EntityId
    decided_at: datetime


@dataclass(frozen=True, slots=True)
class EnforcementView:
    id: EntityId
    case_id: EntityId
    decision_id: EntityId
    action_type: EnforcementType
    target_user_id: EntityId | None
    target_listing_id: EntityId | None
    target_key: str
    ends_at: datetime | None
    status: EnforcementStatus
    rationale: str
    proposed_by: EntityId
    proposed_at: datetime
    approved_by: EntityId | None
    approved_at: datetime | None
    rejected_reason: str | None
    applied_at: datetime | None
    reversed_by: EntityId | None
    reversal_reason: str | None
    reversed_at: datetime | None


@dataclass(frozen=True, slots=True)
class CaseEventView:
    id: EntityId
    case_id: EntityId
    event_type: str
    actor_id: EntityId | None
    occurred_at: datetime
    details: str | None


@dataclass(frozen=True, slots=True)
class ReviewerCaseView:
    id: EntityId
    category: ReportCategory
    priority: CasePriority
    status: CaseStatus
    subject_user_id: EntityId
    assigned_to: EntityId | None
    version: int
    cycle: int
    created_by: EntityId
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None
    linked_reports: tuple[ReviewerReportView, ...]
    evidence_metadata: tuple[EvidenceMetadataView, ...]
    notes: tuple[NoteView, ...]
    decisions: tuple[DecisionView, ...]
    enforcement_actions: tuple[EnforcementView, ...]
    viewer_kind: str


@dataclass(frozen=True, slots=True)
class ApproverCaseView:
    id: EntityId
    category: ReportCategory
    priority: CasePriority
    status: CaseStatus
    subject_user_id: EntityId
    assigned_to: EntityId | None
    version: int
    cycle: int
    created_by: EntityId
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None
    decisions: tuple[DecisionView, ...]
    enforcement_actions: tuple[EnforcementView, ...]


# --- Request DTOs ---

@dataclass(frozen=True, slots=True)
class SubmitReportRequest:
    actor_id: EntityId
    category: ReportCategory
    subject_type: SubjectType
    subject_id: EntityId
    description: str
    idempotency_key: str
    evidence_type: EvidenceType | None = None
    resource_type: str | None = None
    resource_id: EntityId | None = None
    conversation_id: EntityId | None = None
    message_id: EntityId | None = None


@dataclass(frozen=True, slots=True)
class ListMyReportsRequest:
    actor_id: EntityId
    page_request: PageRequest = PageRequest(page=1, page_size=20)


@dataclass(frozen=True, slots=True)
class GetMyReportRequest:
    actor_id: EntityId
    report_id: EntityId


@dataclass(frozen=True, slots=True)
class ListReviewQueueRequest:
    actor_id: EntityId
    category: ReportCategory | None = None
    page_request: PageRequest = PageRequest(page=1, page_size=20)


@dataclass(frozen=True, slots=True)
class OpenCaseFromReportRequest:
    actor_id: EntityId
    report_id: EntityId
    priority: CasePriority = CasePriority.ORDINARY


@dataclass(frozen=True, slots=True)
class LinkReportToCaseRequest:
    actor_id: EntityId
    case_id: EntityId
    report_id: EntityId


@dataclass(frozen=True, slots=True)
class ListCasesRequest:
    actor_id: EntityId
    status: CaseStatus | None = None
    category: ReportCategory | None = None
    assigned_to: EntityId | None = None
    page_request: PageRequest = PageRequest(page=1, page_size=20)


@dataclass(frozen=True, slots=True)
class GetCaseRequest:
    actor_id: EntityId
    case_id: EntityId


@dataclass(frozen=True, slots=True)
class TriageCaseRequest:
    actor_id: EntityId
    case_id: EntityId
    priority: CasePriority


@dataclass(frozen=True, slots=True)
class AssignCaseRequest:
    actor_id: EntityId
    case_id: EntityId
    assignee_id: EntityId | None


@dataclass(frozen=True, slots=True)
class ChangeCaseStatusRequest:
    actor_id: EntityId
    case_id: EntityId
    target_status: CaseStatus


@dataclass(frozen=True, slots=True)
class ViewEvidenceRequest:
    actor_id: EntityId
    evidence_id: EntityId


@dataclass(frozen=True, slots=True)
class AddNoteRequest:
    actor_id: EntityId
    case_id: EntityId
    kind: NoteKind
    content: str
    cited_evidence_ids: tuple[EntityId, ...] = field(default_factory=tuple)
    corrects_note_id: EntityId | None = None


@dataclass(frozen=True, slots=True)
class GetCaseHistoryRequest:
    actor_id: EntityId
    case_id: EntityId


@dataclass(frozen=True, slots=True)
class RecordDecisionRequest:
    actor_id: EntityId
    case_id: EntityId
    decision_type: DecisionType
    rationale: str
    cited_evidence_ids: tuple[EntityId, ...] = field(default_factory=tuple)
    cited_note_ids: tuple[EntityId, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ProposeEnforcementRequest:
    actor_id: EntityId
    case_id: EntityId
    decision_id: EntityId
    action_type: EnforcementType
    target_user_id: EntityId | None = None
    target_listing_id: EntityId | None = None
    ends_at: datetime | None = None
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class ApproveEnforcementRequest:
    actor_id: EntityId
    enforcement_id: EntityId


@dataclass(frozen=True, slots=True)
class RejectEnforcementRequest:
    actor_id: EntityId
    enforcement_id: EntityId
    reason: str


@dataclass(frozen=True, slots=True)
class ReverseEnforcementRequest:
    actor_id: EntityId
    enforcement_id: EntityId
    reason: str


@dataclass(frozen=True, slots=True)
class ProcessEnforcementQueueRequest:
    limit: int = 100


@dataclass(frozen=True, slots=True)
class RequeueFailedEnforcementRequest:
    actor_id: EntityId
    enforcement_id: EntityId


# --- Inbound Use Case Protocols ---

@runtime_checkable
class SubmitReport(Protocol):
    async def execute(self, request: SubmitReportRequest) -> ReportAck:
        ...


@runtime_checkable
class ListMyReports(Protocol):
    async def execute(self, request: ListMyReportsRequest) -> Page[ReporterReportView]:
        ...


@runtime_checkable
class GetMyReport(Protocol):
    async def execute(self, request: GetMyReportRequest) -> ReporterReportView:
        ...


@runtime_checkable
class ListReviewQueue(Protocol):
    async def execute(self, request: ListReviewQueueRequest) -> Page[ReviewerReportView]:
        ...


@runtime_checkable
class OpenCaseFromReport(Protocol):
    async def execute(self, request: OpenCaseFromReportRequest) -> ReviewerCaseView:
        ...


@runtime_checkable
class LinkReportToCase(Protocol):
    async def execute(self, request: LinkReportToCaseRequest) -> None:
        ...


@runtime_checkable
class ListCases(Protocol):
    async def execute(self, request: ListCasesRequest) -> Page[ReviewerCaseView]:
        ...


@runtime_checkable
class GetCase(Protocol):
    async def execute(self, request: GetCaseRequest) -> ReviewerCaseView | ApproverCaseView:
        ...


@runtime_checkable
class TriageCase(Protocol):
    async def execute(self, request: TriageCaseRequest) -> ReviewerCaseView:
        ...


@runtime_checkable
class AssignCase(Protocol):
    async def execute(self, request: AssignCaseRequest) -> ReviewerCaseView:
        ...


@runtime_checkable
class ChangeCaseStatus(Protocol):
    async def execute(self, request: ChangeCaseStatusRequest) -> ReviewerCaseView:
        ...


@runtime_checkable
class ViewEvidence(Protocol):
    async def execute(self, request: ViewEvidenceRequest) -> EvidenceContentView:
        ...


@runtime_checkable
class AddNote(Protocol):
    async def execute(self, request: AddNoteRequest) -> NoteView:
        ...


@runtime_checkable
class GetCaseHistory(Protocol):
    async def execute(self, request: GetCaseHistoryRequest) -> list[CaseEventView]:
        ...


@runtime_checkable
class RecordDecision(Protocol):
    async def execute(self, request: RecordDecisionRequest) -> DecisionView:
        ...


@runtime_checkable
class ProposeEnforcement(Protocol):
    async def execute(self, request: ProposeEnforcementRequest) -> EnforcementView:
        ...


@runtime_checkable
class ApproveEnforcement(Protocol):
    async def execute(self, request: ApproveEnforcementRequest) -> EnforcementView:
        ...


@runtime_checkable
class RejectEnforcement(Protocol):
    async def execute(self, request: RejectEnforcementRequest) -> EnforcementView:
        ...


@runtime_checkable
class ReverseEnforcement(Protocol):
    async def execute(self, request: ReverseEnforcementRequest) -> EnforcementView:
        ...


@runtime_checkable
class ProcessEnforcementQueue(Protocol):
    async def execute(self, request: ProcessEnforcementQueueRequest) -> dict[str, int]:
        ...


@runtime_checkable
class RequeueFailedEnforcement(Protocol):
    async def execute(self, request: RequeueFailedEnforcementRequest) -> EnforcementView:
        ...
