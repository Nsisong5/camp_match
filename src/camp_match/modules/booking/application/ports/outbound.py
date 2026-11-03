from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from camp_match.modules.booking.domain.entities import Booking
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.modules.verification.domain.value_objects import VerificationTargetType
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, slots=True)
class ListingSummary:
    id: EntityId
    unit_id: EntityId
    property_id: EntityId
    status: str
    price_amount_kobo: int
    price_currency: str
    price_period: str


@dataclass(frozen=True, slots=True)
class VerificationStatusDTO:
    is_verified: bool
    verified_on: date | datetime | None


class HousingProvider(Protocol):
    async def get_listing(self, listing_id: EntityId) -> ListingSummary | None:
        ...

    async def get_property_owner(self, property_id: EntityId) -> EntityId | None:
        ...

    async def check_availability(self, unit_id: EntityId) -> int:
        ...

    async def reserve_slot(self, unit_id: EntityId) -> bool:
        ...

    async def release_slot(self, unit_id: EntityId) -> None:
        ...


class VerificationProvider(Protocol):
    async def get_verification_status(
        self, target_type: VerificationTargetType, target_id: EntityId
    ) -> VerificationStatusDTO:
        ...


class AuthorizationService(Protocol):
    async def authorize(
        self,
        identity_id: EntityId,
        permission: Permission,
        resource_owner_id: EntityId | None = None,
    ) -> None:
        ...


class BookingRepository(Protocol):
    async def add(self, booking: Booking) -> Booking:
        ...

    async def get_by_id(self, booking_id: EntityId) -> Booking | None:
        ...

    async def get_by_idempotency_key(
        self, student_id: EntityId, idempotency_key: str
    ) -> Booking | None:
        ...

    async def find_by_student(
        self, student_id: EntityId, page: PageRequest
    ) -> Page[Booking]:
        ...

    async def find_by_property(
        self, property_id: EntityId, page: PageRequest
    ) -> Page[Booking]:
        ...

    async def find_expired_holds(self, as_of: datetime) -> list[Booking]:
        ...

    async def confirm(self, booking_id: EntityId, confirmed_at: datetime) -> bool:
        ...

    async def cancel(
        self,
        booking_id: EntityId,
        cancelled_at: datetime,
        cancelled_by: EntityId,
        cancellation_reason: str,
    ) -> bool:
        ...

    async def expire(self, booking_id: EntityId) -> bool:
        ...

    async def confirm_handover_offered(
        self, booking_id: EntityId, offered_at: datetime, offered_by: EntityId
    ) -> bool:
        ...

    async def confirm_handover_accepted(
        self, booking_id: EntityId, accepted_at: datetime
    ) -> bool:
        ...
