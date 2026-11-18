"""Review schemas adapter."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageSchema(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class TransactionReviewListItemSchema(BaseModel):
    payment_id: UUID
    booking_id: UUID
    student_id: UUID
    provider_id: UUID | None = None
    amount_kobo: int
    currency: str
    paid_at: datetime
    stage: str
    next_action: str
    next_action_since: datetime | None = None
    released_kobo: int
    refunded_kobo: int
    warnings_sent: int | None = None
    warnings_required: int | None = None
    open_dispute: bool
    can_release: bool


class PartySchema(BaseModel):
    id: UUID
    display_name: str | None = None


class PartiesSchema(BaseModel):
    student: PartySchema
    provider: PartySchema | None = None


class ListingDetailSchema(BaseModel):
    listing_id: UUID | None = None
    property_id: UUID | None = None
    title: str | None = None
    property_name: str | None = None


class HandoverDetailSchema(BaseModel):
    offered_at: datetime | None = None
    accepted_at: datetime | None = None
    student_confirmed: bool = False


class BookingDetailSchema(BaseModel):
    id: UUID
    status: str
    handover: HandoverDetailSchema


class FundsDetailSchema(BaseModel):
    held_kobo: int
    released_kobo: int
    refunded_kobo: int
    remaining_kobo: int
    disposition_status: str


class DecisionItemSchema(BaseModel):
    id: UUID
    decision: str
    amount_kobo: int
    origin: str
    triggering_fact: str
    decided_at: datetime
    authorized_by: UUID
    student_confirmed_at: datetime | None = None


class WarningItemSchema(BaseModel):
    number: int
    stage: str
    due_at: datetime
    sent_at: datetime | None = None


class WarningsGroupSchema(BaseModel):
    required: int
    sent: int
    items: list[WarningItemSchema]


class ReleaseAutoSchema(BaseModel):
    enabled: bool
    delay_hours: int
    cycle: int | None = None
    window_starts_at: datetime | None = None
    earliest_auto_release_at: datetime | None = None
    blocking_reason: str | None = None
    warnings: WarningsGroupSchema


class ReleaseDetailSchema(BaseModel):
    eligible_now: bool
    blocking_reason: str | None = None
    decisions: list[DecisionItemSchema]
    auto: ReleaseAutoSchema


class OperationItemSchema(BaseModel):
    id: UUID
    amount_kobo: int
    status: str
    requested_at: datetime
    confirmed_at: datetime | None = None
    failure_reason: str | None = None


class OperationsDetailSchema(BaseModel):
    releases: list[OperationItemSchema]
    refunds: list[OperationItemSchema]


class DisputeDetailSchema(BaseModel):
    id: UUID
    status: str
    raised_at: datetime
    raised_by: UUID
    reason: str
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None
    resolution_notes: str | None = None


class AttemptDetailSchema(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    confirmed_at: datetime | None = None


class LedgerEntryDetailSchema(BaseModel):
    type: str
    amount_kobo: int
    created_at: datetime


class LedgerDetailSchema(BaseModel):
    balanced: bool
    entries: list[LedgerEntryDetailSchema]


class ActorSchema(BaseModel):
    type: str
    id: UUID | None = None


class TimelineItemSchema(BaseModel):
    at: datetime
    kind: str
    actor: ActorSchema
    detail: dict[str, Any] = Field(default_factory=dict)


class ActionPermissionSchema(BaseModel):
    allowed: bool
    reason: str | None = None


class AvailableActionsSchema(BaseModel):
    release: ActionPermissionSchema
    refund: ActionPermissionSchema
    resolve_dispute: ActionPermissionSchema


class TransactionReviewDetailSchema(BaseModel):
    as_of: datetime
    transaction: dict[str, Any]
    parties: PartiesSchema
    listing: ListingDetailSchema
    context_status: str
    booking: BookingDetailSchema
    funds: FundsDetailSchema
    release: ReleaseDetailSchema
    operations: OperationsDetailSchema
    disputes: list[DisputeDetailSchema]
    attempts: list[AttemptDetailSchema]
    ledger: LedgerDetailSchema
    timeline: list[TimelineItemSchema]
    available_actions: AvailableActionsSchema


class TransactionReviewSummarySchema(BaseModel):
    by_stage: dict[str, int]
    by_next_action: dict[str, int]
    release_due_oldest_since: datetime | None = None
    warnings_pending: int
    auto_release_enabled: bool


class TaskSubjectSchema(BaseModel):
    type: str
    id: UUID


class TaskTargetSchema(BaseModel):
    type: str
    id: UUID


class TaskItemSchema(BaseModel):
    task_id: str
    type: str
    priority: str
    since: datetime
    due_at: datetime | None = None
    subject: TaskSubjectSchema
    target: TaskTargetSchema
    facts: dict[str, Any]
    required_permission: str
    can_act: bool


class TaskSectionSchema(BaseModel):
    source: str
    status: str
    as_of: datetime
    total: int | None = None
    items: list[TaskItemSchema]
    reason_code: str | None = None


class TasksOverviewResponseSchema(BaseModel):
    as_of: datetime
    sections: list[TaskSectionSchema]
