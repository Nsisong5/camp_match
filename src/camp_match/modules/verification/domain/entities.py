from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass
class VerificationCase:
    id: EntityId
    target_type: VerificationTargetType
    target_id: EntityId
    status: VerificationStatus
    submitted_by: EntityId
    previous_case_id: EntityId | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: EntityId | None = None
    revocation_reason: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def is_currently_valid(self, now: datetime | None = None) -> bool:
        if self.status != VerificationStatus.VERIFIED:
            return False
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None:
            current_time = now or datetime.now(timezone.utc)
            # Handle naive vs aware datetime comparison safely
            if self.expires_at.tzinfo is not None and current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone.utc)
            elif self.expires_at.tzinfo is None and current_time.tzinfo is not None:
                current_time = current_time.replace(tzinfo=None)
            if self.expires_at <= current_time:
                return False
        return True


@dataclass
class Evidence:
    id: EntityId
    verification_case_id: EntityId
    evidence_type: EvidenceType
    media_id: EntityId
    submitted_by: EntityId
    source_description: str | None = None
    captured_at: datetime | None = None
    inspection_id: EntityId | None = None
    review_status: EvidenceReviewStatus = EvidenceReviewStatus.PENDING
    review_notes: str | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def update_review(self, status: EvidenceReviewStatus, notes: str | None, parent_case_status: VerificationStatus) -> None:
        terminal_statuses = {
            VerificationStatus.VERIFIED,
            VerificationStatus.REJECTED,
            VerificationStatus.REVOKED,
            VerificationStatus.CANCELLED,
        }
        if parent_case_status in terminal_statuses:
            raise ValueError("Cannot update evidence review after parent verification case has reached a terminal decision.")
        self.review_status = status
        self.review_notes = notes


@dataclass
class Inspection:
    id: EntityId
    verification_case_id: EntityId
    inspector_id: EntityId
    assigned_by: EntityId
    status: InspectionStatus = InspectionStatus.ASSIGNED
    assigned_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: InspectionResult | None = None
    notes: str | None = None


@dataclass
class InspectionObservation:
    id: EntityId
    inspection_id: EntityId
    item: ChecklistItem
    passed: bool
    notes: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class VerificationDecision:
    id: EntityId
    verification_case_id: EntityId
    outcome: DecisionOutcome
    reason: str
    decided_by: EntityId
    decided_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.reason or not self.reason.strip():
            raise ValueError("Verification decision reason is required and cannot be empty.")
