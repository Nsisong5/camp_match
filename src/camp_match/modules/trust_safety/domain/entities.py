from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from camp_match.modules.trust_safety.domain.errors import (
    InvalidCaseTransition,
    InvalidEnforcementTransition,
)
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
    ReportDescription,
    ReportStatus,
    SubjectType,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass
class Report:
    id: EntityId
    reporter_id: EntityId
    category: ReportCategory
    subject_type: SubjectType
    subject_id: EntityId
    subject_user_id: EntityId
    description: ReportDescription
    status: ReportStatus
    idempotency_key: str
    request_fingerprint: str
    created_at: datetime

    def __post_init__(self) -> None:
        if self.reporter_id == self.subject_user_id:
            raise ValueError("Reporter cannot equal subject user.")


@dataclass
class EvidenceItem:
    id: EntityId
    report_id: EntityId
    evidence_type: EvidenceType
    resource_type: str
    resource_id: EntityId
    conversation_id: EntityId | None
    snapshot: dict[str, Any] | None
    content_sha256: str | None
    collected_by: EntityId
    collected_at: datetime
    source: str
    confidentiality: Confidentiality

    def __post_init__(self) -> None:
        if self.evidence_type == EvidenceType.MESSAGE_SNAPSHOT:
            if (
                self.snapshot is None
                or self.content_sha256 is None
                or self.confidentiality != Confidentiality.RESTRICTED
            ):
                raise ValueError(
                    "MESSAGE_SNAPSHOT requires snapshot, hash, and "
                    "RESTRICTED confidentiality."
                )
            canonical = json.dumps(self.snapshot, sort_keys=True, separators=(",", ":"))
            computed_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if computed_hash != self.content_sha256:
                raise ValueError("Evidence snapshot hash verification failed.")


@dataclass
class SafetyCase:
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
    resolved_at: datetime | None = None
    closed_at: datetime | None = None

    def transition(self, target: CaseStatus, now: datetime) -> None:
        current = self.status
        allowed = {
            (CaseStatus.OPEN, CaseStatus.TRIAGED),
            (CaseStatus.TRIAGED, CaseStatus.IN_REVIEW),
            (CaseStatus.IN_REVIEW, CaseStatus.AWAITING_INFORMATION),
            (CaseStatus.AWAITING_INFORMATION, CaseStatus.IN_REVIEW),
            (CaseStatus.TRIAGED, CaseStatus.ESCALATED),
            (CaseStatus.IN_REVIEW, CaseStatus.ESCALATED),
            (CaseStatus.ESCALATED, CaseStatus.IN_REVIEW),
            (CaseStatus.IN_REVIEW, CaseStatus.RESOLVED),
            (CaseStatus.ESCALATED, CaseStatus.RESOLVED),
            (CaseStatus.RESOLVED, CaseStatus.CLOSED),
            (CaseStatus.RESOLVED, CaseStatus.IN_REVIEW),
            (CaseStatus.CLOSED, CaseStatus.IN_REVIEW),
        }
        if (current, target) not in allowed:
            raise InvalidCaseTransition(f"Invalid case transition from {current} to {target}.")
        
        self.status = target
        self.version += 1
        self.updated_at = now
        if target == CaseStatus.RESOLVED:
            self.resolved_at = now
        elif target == CaseStatus.CLOSED:
            self.closed_at = now
        elif target == CaseStatus.IN_REVIEW and current in {CaseStatus.RESOLVED, CaseStatus.CLOSED}:
            self.cycle += 1
            self.resolved_at = None
            self.closed_at = None


@dataclass
class InvestigationNote:
    id: EntityId
    case_id: EntityId
    author_id: EntityId
    kind: NoteKind
    content: str
    cited_evidence_ids: tuple[EntityId, ...] = field(default_factory=tuple)
    corrects_note_id: EntityId | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not (1 <= len(self.content) <= 2000):
            raise ValueError("Note content length must be between 1 and 2000 characters.")
        if self.kind == NoteKind.CORROBORATED_FACT and not self.cited_evidence_ids:
            raise ValueError("CORROBORATED_FACT notes must cite at least one evidence item.")


@dataclass
class CaseDecision:
    id: EntityId
    case_id: EntityId
    cycle: int
    decision_type: DecisionType
    rationale: str
    cited_evidence_ids: tuple[EntityId, ...] = field(default_factory=tuple)
    cited_note_ids: tuple[EntityId, ...] = field(default_factory=tuple)
    decided_by: EntityId = field(default_factory=EntityId.new)
    decided_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_final(self) -> bool:
        return self.decision_type != DecisionType.FURTHER_INVESTIGATION_REQUIRED

    def __post_init__(self) -> None:
        if not (10 <= len(self.rationale) <= 2000):
            raise ValueError("Decision rationale length must be between 10 and 2000 characters.")
        if self.decision_type == DecisionType.VIOLATION_ESTABLISHED and not self.cited_note_ids:
            raise ValueError("VIOLATION_ESTABLISHED decision requires at least one cited note.")


@dataclass
class EnforcementAction:
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
    approved_by: EntityId | None = None
    approved_at: datetime | None = None
    rejected_reason: str | None = None
    attempts: int = 0
    next_attempt_at: datetime | None = None
    last_error: str | None = None
    applied_at: datetime | None = None
    reversed_by: EntityId | None = None
    reversal_reason: str | None = None
    reversed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.action_type == EnforcementType.LISTING_SUSPENSION:
            if self.target_listing_id is None or self.target_user_id is not None:
                raise ValueError(
                    "LISTING_SUSPENSION requires target_listing_id and no target_user_id."
                )
        else:
            if self.target_user_id is None or self.target_listing_id is not None:
                raise ValueError(
                    f"{self.action_type} requires target_user_id and no target_listing_id."
                )

        if (
            self.action_type == EnforcementType.COMMUNICATION_RESTRICTION
            and self.ends_at is None
        ):
            raise ValueError("COMMUNICATION_RESTRICTION requires ends_at.")
        if (
            self.action_type != EnforcementType.COMMUNICATION_RESTRICTION
            and self.ends_at is not None
        ):
            raise ValueError(f"{self.action_type} cannot have ends_at.")

    def transition(self, target: EnforcementStatus) -> None:
        current = self.status
        allowed = {
            (EnforcementStatus.PROPOSED, EnforcementStatus.APPROVED),
            (EnforcementStatus.PROPOSED, EnforcementStatus.REJECTED),
            (EnforcementStatus.APPROVED, EnforcementStatus.APPLIED),
            (EnforcementStatus.APPROVED, EnforcementStatus.FAILED),
            (EnforcementStatus.FAILED, EnforcementStatus.APPROVED),
            (EnforcementStatus.APPLIED, EnforcementStatus.REVERSAL_PENDING),
            (EnforcementStatus.REVERSAL_PENDING, EnforcementStatus.REVERSED),
            (EnforcementStatus.REVERSAL_PENDING, EnforcementStatus.REVERSAL_FAILED),
            (EnforcementStatus.REVERSAL_FAILED, EnforcementStatus.REVERSAL_PENDING),
            (EnforcementStatus.APPLIED, EnforcementStatus.EXPIRED),
        }
        if (current, target) not in allowed:
            raise InvalidEnforcementTransition(
                f"Invalid enforcement transition from {current} to {target}."
            )
        self.status = target
