"""Trust & Safety outbound ports (repositories, providers, enforcers)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from camp_match.modules.trust_safety.domain.entities import (
    CaseDecision,
    EnforcementAction,
    EvidenceItem,
    InvestigationNote,
    Report,
    SafetyCase,
)
from camp_match.modules.trust_safety.domain.value_objects import (
    EnforcementStatus,
    ReportCategory,
    SubjectType,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, slots=True)
class ListingSubject:
    listing_id: EntityId
    owner_id: EntityId
    status: str


@dataclass(frozen=True, slots=True)
class BookingSubject:
    booking_id: EntityId
    student_id: EntityId
    provider_id: EntityId


@dataclass(frozen=True, slots=True)
class MessageSnapshotSource:
    message_id: EntityId
    conversation_id: EntityId
    sender_id: EntityId
    content: str
    sequence: int
    created_at: datetime


_DEFAULT_PAGE_REQUEST = PageRequest(page=1, page_size=20)


@runtime_checkable
class ReportRepository(Protocol):
    async def add(self, report: Report) -> None:
        ...

    async def get_by_id(self, report_id: EntityId) -> Report | None:
        ...

    async def get_by_idempotency_key(
        self, reporter_id: EntityId, idempotency_key: str
    ) -> Report | None:
        ...

    async def list_by_reporter(
        self, reporter_id: EntityId, page_request: PageRequest
    ) -> Page[Report]:
        ...

    async def list_by_case_id(self, case_id: EntityId) -> list[Report]:
        ...

    async def list_unlinked(
        self, category: ReportCategory | None, page_request: PageRequest
    ) -> Page[Report]:
        ...

    async def update_status(self, report_id: EntityId, status: str) -> None:
        ...

    async def count_recent_by_reporter(
        self, reporter_id: EntityId, since: datetime
    ) -> int:
        ...

    async def similar_report_count(
        self,
        subject_type: SubjectType,
        subject_id: EntityId,
        excluding_report_id: EntityId,
    ) -> int:
        ...


@runtime_checkable
class CaseRepository(Protocol):
    async def add(self, case: SafetyCase) -> None:
        ...

    async def get_by_id(self, case_id: EntityId) -> SafetyCase | None:
        ...

    async def update(self, case: SafetyCase, expected_version: int) -> bool:
        ...

    async def link_report(self, case_id: EntityId, report_id: EntityId) -> None:
        ...

    async def list_cases(
        self,
        status: Any | None = None,
        category: ReportCategory | None = None,
        assigned_to: EntityId | None = None,
        page_request: PageRequest = _DEFAULT_PAGE_REQUEST,
    ) -> Page[SafetyCase]:
        ...

    async def add_event(
        self,
        case_id: EntityId,
        event_type: str,
        actor_id: EntityId | None,
        details: str | None,
    ) -> None:
        ...

    async def list_events(self, case_id: EntityId) -> list[Any]:
        ...


@runtime_checkable
class EvidenceRepository(Protocol):
    async def add(self, evidence: EvidenceItem) -> None:
        ...

    async def get_by_id(self, evidence_id: EntityId) -> EvidenceItem | None:
        ...

    async def list_by_case_id(self, case_id: EntityId) -> list[EvidenceItem]:
        ...

    async def list_by_report_id(self, report_id: EntityId) -> list[EvidenceItem]:
        ...


@runtime_checkable
class NoteRepository(Protocol):
    async def add(self, note: InvestigationNote) -> None:
        ...

    async def list_by_case_id(self, case_id: EntityId) -> list[InvestigationNote]:
        ...


@runtime_checkable
class DecisionRepository(Protocol):
    async def add(self, decision: CaseDecision) -> None:
        ...

    async def list_by_case_id(self, case_id: EntityId) -> list[CaseDecision]:
        ...


@runtime_checkable
class EnforcementRepository(Protocol):
    async def add(self, action: EnforcementAction) -> None:
        ...

    async def get_by_id(self, action_id: EntityId) -> EnforcementAction | None:
        ...

    async def update(self, action: EnforcementAction, expected_status: EnforcementStatus) -> bool:
        ...

    async def claim_for_attempt(
        self, action_id: EntityId, next_attempt_at: datetime
    ) -> EnforcementAction | None:
        ...

    async def list_due(self, now: datetime, limit: int) -> list[EnforcementAction]:
        ...

    async def list_by_case_id(self, case_id: EntityId) -> list[EnforcementAction]:
        ...


@runtime_checkable
class ListingSubjectProvider(Protocol):
    async def get_listing(self, listing_id: EntityId, viewer_id: EntityId) -> ListingSubject | None:
        ...


@runtime_checkable
class BookingSubjectProvider(Protocol):
    async def get_booking(self, booking_id: EntityId, viewer_id: EntityId) -> BookingSubject | None:
        ...


@runtime_checkable
class MessageEvidenceProvider(Protocol):
    async def get_message(
        self, viewer_id: EntityId, conversation_id: EntityId, message_id: EntityId
    ) -> MessageSnapshotSource | None:
        ...


@runtime_checkable
class AccountEnforcer(Protocol):
    async def disable(self, identity_id: EntityId) -> None:
        ...

    async def reactivate(self, identity_id: EntityId) -> None:
        ...


@runtime_checkable
class ListingEnforcer(Protocol):
    async def suspend(self, actor_id: EntityId, listing_id: EntityId, reference: EntityId) -> None:
        ...

    async def lift(self, actor_id: EntityId, listing_id: EntityId, reference: EntityId) -> None:
        ...


@runtime_checkable
class CommunicationEnforcer(Protocol):
    async def restrict(
        self, actor_id: EntityId, user_id: EntityId, ends_at: datetime, reference: EntityId
    ) -> None:
        ...

    async def lift(self, actor_id: EntityId, reference: EntityId) -> None:
        ...
