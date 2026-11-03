from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

from camp_match.modules.verification.application.ports.outbound import AccessGrant
from camp_match.modules.verification.domain.value_objects import (
    ChecklistItem,
    EvidenceReviewStatus,
    EvidenceType,
    InspectionResult,
    VerificationStatus,
    VerificationTargetType,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, slots=True)
class AddEvidenceRequest:
    case_id: EntityId
    evidence_type: EvidenceType
    content: bytes
    content_type: str
    source_description: str | None = None
    captured_at: datetime | None = None
    caller_id: EntityId = EntityId.new()


@dataclass(frozen=True, slots=True)
class AddEvidenceResponse:
    evidence_id: EntityId


class AddEvidence(Protocol):
    async def execute(self, request: AddEvidenceRequest) -> AddEvidenceResponse:
        ...


@dataclass(frozen=True, slots=True)
class ReviewEvidenceRequest:
    evidence_id: EntityId
    review_status: EvidenceReviewStatus
    notes: str | None = None
    caller_id: EntityId = EntityId.new()


@dataclass(frozen=True, slots=True)
class ReviewEvidenceResponse:
    evidence_id: EntityId
    review_status: EvidenceReviewStatus


class ReviewEvidence(Protocol):
    async def execute(self, request: ReviewEvidenceRequest) -> ReviewEvidenceResponse:
        ...


@dataclass(frozen=True, slots=True)
class GetEvidenceAccessRequest:
    evidence_id: EntityId
    caller_id: EntityId


class GetEvidenceAccess(Protocol):
    async def execute(self, request: GetEvidenceAccessRequest) -> AccessGrant:
        ...


@dataclass(frozen=True, slots=True)
class AssignInspectorRequest:
    case_id: EntityId
    inspector_id: EntityId
    caller_id: EntityId


@dataclass(frozen=True, slots=True)
class AssignInspectorResponse:
    inspection_id: EntityId


class AssignInspector(Protocol):
    async def execute(self, request: AssignInspectorRequest) -> AssignInspectorResponse:
        ...


@dataclass(frozen=True, slots=True)
class StartInspectionRequest:
    inspection_id: EntityId
    caller_id: EntityId


@dataclass(frozen=True, slots=True)
class StartInspectionResponse:
    inspection_id: EntityId


class StartInspection(Protocol):
    async def execute(self, request: StartInspectionRequest) -> StartInspectionResponse:
        ...


@dataclass(frozen=True, slots=True)
class RecordInspectionObservationRequest:
    inspection_id: EntityId
    item: ChecklistItem
    passed: bool
    notes: str | None = None
    caller_id: EntityId = EntityId.new()


@dataclass(frozen=True, slots=True)
class RecordInspectionObservationResponse:
    observation_id: EntityId


class RecordInspectionObservation(Protocol):
    async def execute(
        self, request: RecordInspectionObservationRequest
    ) -> RecordInspectionObservationResponse:
        ...


@dataclass(frozen=True, slots=True)
class CompleteInspectionRequest:
    inspection_id: EntityId
    caller_id: EntityId


@dataclass(frozen=True, slots=True)
class CompleteInspectionResponse:
    inspection_id: EntityId
    result: InspectionResult


class CompleteInspection(Protocol):
    async def execute(self, request: CompleteInspectionRequest) -> CompleteInspectionResponse:
        ...


@dataclass(frozen=True, slots=True)
class StartReviewRequest:
    case_id: EntityId
    caller_id: EntityId


class StartReview(Protocol):
    async def execute(self, request: StartReviewRequest) -> None:
        ...


@dataclass(frozen=True, slots=True)
class RequestInspectionRequest:
    case_id: EntityId
    caller_id: EntityId


class RequestInspection(Protocol):
    async def execute(self, request: RequestInspectionRequest) -> None:
        ...


@dataclass(frozen=True, slots=True)
class MarkReadyForDecisionRequest:
    case_id: EntityId
    caller_id: EntityId


class MarkReadyForDecision(Protocol):
    async def execute(self, request: MarkReadyForDecisionRequest) -> None:
        ...


@dataclass(frozen=True, slots=True)
class ApproveVerificationRequest:
    case_id: EntityId
    reason: str
    caller_id: EntityId


@dataclass(frozen=True, slots=True)
class ApproveVerificationResponse:
    case_id: EntityId
    expires_at: datetime


class ApproveVerification(Protocol):
    async def execute(self, request: ApproveVerificationRequest) -> ApproveVerificationResponse:
        ...


@dataclass(frozen=True, slots=True)
class RejectVerificationRequest:
    case_id: EntityId
    reason: str
    caller_id: EntityId


class RejectVerification(Protocol):
    async def execute(self, request: RejectVerificationRequest) -> None:
        ...


@dataclass(frozen=True, slots=True)
class RevokeVerificationRequest:
    case_id: EntityId
    revocation_reason: str
    caller_id: EntityId


class RevokeVerification(Protocol):
    async def execute(self, request: RevokeVerificationRequest) -> None:
        ...


@dataclass(frozen=True, slots=True)
class CreateVerificationCaseRequest:
    target_type: VerificationTargetType
    target_id: EntityId
    caller_id: EntityId


@dataclass(frozen=True, slots=True)
class CreateVerificationCaseResponse:
    case_id: EntityId


class CreateVerificationCase(Protocol):
    async def execute(self, request: CreateVerificationCaseRequest) -> CreateVerificationCaseResponse:
        ...


@dataclass(frozen=True, slots=True)
class SubmitVerificationCaseRequest:
    case_id: EntityId
    caller_id: EntityId


class SubmitVerificationCase(Protocol):
    async def execute(self, request: SubmitVerificationCaseRequest) -> None:
        ...


@dataclass(frozen=True, slots=True)
class EvidenceOwnerDTO:
    id: EntityId
    evidence_type: EvidenceType
    media_id: EntityId
    submitted_by: EntityId
    source_description: str | None
    captured_at: datetime | None
    review_status: EvidenceReviewStatus


@dataclass(frozen=True, slots=True)
class EvidenceReviewerDTO:
    id: EntityId
    evidence_type: EvidenceType
    media_id: EntityId
    submitted_by: EntityId
    source_description: str | None
    captured_at: datetime | None
    review_status: EvidenceReviewStatus
    review_notes: str | None


@dataclass(frozen=True, slots=True)
class VerificationCaseOwnerDTO:
    id: EntityId
    target_type: VerificationTargetType
    target_id: EntityId
    status: VerificationStatus
    submitted_by: EntityId
    expires_at: datetime | None
    evidence: list[EvidenceOwnerDTO]


@dataclass(frozen=True, slots=True)
class VerificationCaseReviewerDTO:
    id: EntityId
    target_type: VerificationTargetType
    target_id: EntityId
    status: VerificationStatus
    submitted_by: EntityId
    expires_at: datetime | None
    evidence: list[EvidenceReviewerDTO]
    history: list[Any]


@dataclass(frozen=True, slots=True)
class GetVerificationCaseRequest:
    case_id: EntityId
    caller_id: EntityId
    is_reviewer: bool = False


class GetVerificationCase(Protocol):
    async def execute(
        self, request: GetVerificationCaseRequest
    ) -> VerificationCaseOwnerDTO | VerificationCaseReviewerDTO:
        ...


@dataclass(frozen=True, slots=True)
class GetVerificationStatusRequest:
    target_type: VerificationTargetType
    target_id: EntityId


@dataclass(frozen=True, slots=True)
class VerificationStatusResponse:
    is_verified: bool
    verified_on: date | None


class GetVerificationStatus(Protocol):
    async def execute(self, request: GetVerificationStatusRequest) -> VerificationStatusResponse:
        ...


@dataclass(frozen=True, slots=True)
class ListMyVerificationCasesRequest:
    caller_id: EntityId


class ListMyVerificationCases(Protocol):
    async def execute(self, request: ListMyVerificationCasesRequest) -> list[Any]:
        ...


@dataclass(frozen=True, slots=True)
class ListMyInspectionsRequest:
    caller_id: EntityId


class ListMyInspections(Protocol):
    async def execute(self, request: ListMyInspectionsRequest) -> list[Any]:
        ...


@dataclass(frozen=True, slots=True)
class ListPendingReviewsRequest:
    caller_id: EntityId


class ListPendingReviews(Protocol):
    async def execute(self, request: ListPendingReviewsRequest) -> list[Any]:
        ...
