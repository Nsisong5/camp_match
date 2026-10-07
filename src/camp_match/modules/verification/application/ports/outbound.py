from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TYPE_CHECKING

from camp_match.modules.verification.domain.value_objects import (
    VerificationStatus,
    VerificationTargetType,
)

if TYPE_CHECKING:
    from camp_match.shared_kernel.domain.identifiers import EntityId
    from camp_match.modules.verification.domain.entities import (
        VerificationCase,
        Evidence,
        Inspection,
        InspectionObservation,
        VerificationDecision,
    )
    from camp_match.modules.security.domain.value_objects import Permission


@dataclass(frozen=True, slots=True)
class AccessGrant:
    token: str
    expires_at: datetime


class MediaProvider(Protocol):
    async def upload(
        self, purpose: str, content: bytes, content_type: str, uploaded_by: EntityId
    ) -> EntityId:
        ...

    async def get_access(self, media_id: EntityId) -> AccessGrant:
        ...


class HousingProvider(Protocol):
    async def get_property_owner(self, property_id: EntityId) -> EntityId | None:
        ...


class ProfileProvider(Protocol):
    async def is_scout(self, identity_id: EntityId) -> bool:
        ...


class AuthorizationService(Protocol):
    async def authorize(
        self,
        identity_id: EntityId,
        permission: Permission,
        resource_owner_id: EntityId | None = None,
    ) -> None:
        ...


class VerificationCaseRepository(Protocol):
    async def add(self, case: VerificationCase) -> None:
        ...

    async def get_by_id(self, case_id: EntityId) -> VerificationCase | None:
        ...

    async def get_latest_by_target(
        self, target_type: VerificationTargetType, target_id: EntityId
    ) -> VerificationCase | None:
        ...

    async def list_by_submitter(self, submitter_id: EntityId) -> list[VerificationCase]:
        ...

    async def list_pending_review(self) -> list[VerificationCase]:
        ...

    async def update(self, case: VerificationCase) -> None:
        ...

    async def update_status_conditionally(
        self,
        case_id: EntityId,
        expected_status: VerificationStatus,
        new_status: VerificationStatus,
        expires_at: datetime | None = None,
        revoked_at: datetime | None = None,
        revoked_by: EntityId | None = None,
        revocation_reason: str | None = None,
    ) -> bool:
        ...


class EvidenceRepository(Protocol):
    async def add(self, evidence: Evidence) -> None:
        ...

    async def get_by_id(self, evidence_id: EntityId) -> Evidence | None:
        ...

    async def list_by_case_id(self, case_id: EntityId) -> list[Evidence]:
        ...

    async def update(self, evidence: Evidence) -> None:
        ...


class InspectionRepository(Protocol):
    async def add(self, inspection: Inspection) -> None:
        ...

    async def get_by_id(self, inspection_id: EntityId) -> Inspection | None:
        ...

    async def get_active_by_case_id(self, case_id: EntityId) -> Inspection | None:
        ...

    async def get_latest_by_case_id(self, case_id: EntityId) -> Inspection | None:
        ...

    async def list_by_inspector(self, inspector_id: EntityId) -> list[Inspection]:
        ...

    async def update(self, inspection: Inspection) -> None:
        ...


class InspectionObservationRepository(Protocol):
    async def add(self, observation: InspectionObservation) -> None:
        ...

    async def list_by_inspection_id(self, inspection_id: EntityId) -> list[InspectionObservation]:
        ...


class VerificationDecisionRepository(Protocol):
    async def add(self, decision: VerificationDecision) -> None:
        ...

    async def get_by_case_id(self, case_id: EntityId) -> VerificationDecision | None:
        ...


class HistoryRepository(Protocol):
    async def add(
        self,
        case_id: EntityId,
        event_type: str,
        actor_id: EntityId | None,
        details: str | None,
    ) -> None:
        ...

    async def list_by_case_id(self, case_id: EntityId) -> list[dict]:
        ...
