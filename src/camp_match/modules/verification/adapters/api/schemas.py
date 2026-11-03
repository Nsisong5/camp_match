from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from camp_match.modules.verification.domain.value_objects import (
    ChecklistItem,
    EvidenceReviewStatus,
    VerificationStatus,
    VerificationTargetType,
)


class CreateVerificationCaseSchema(BaseModel):
    target_type: VerificationTargetType
    target_id: UUID


class VerificationCaseResponseSchema(BaseModel):
    id: UUID
    target_type: VerificationTargetType
    target_id: UUID
    status: VerificationStatus
    submitted_by: UUID
    expires_at: datetime | None = None
    evidence: list[dict] = []
    history: list[dict] | None = None


class ReviewEvidenceSchema(BaseModel):
    review_status: EvidenceReviewStatus
    notes: str | None = None


class AssignInspectorSchema(BaseModel):
    inspector_id: UUID


class RecordObservationSchema(BaseModel):
    item: ChecklistItem
    passed: bool
    notes: str | None = None


class DecisionSchema(BaseModel):
    reason: str


class RevokeSchema(BaseModel):
    revocation_reason: str


class VerificationStatusResponseSchema(BaseModel):
    is_verified: bool
    verified_on: date | None = None
