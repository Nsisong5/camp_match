from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from camp_match.modules.booking.domain.entities import Booking
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True, slots=True)
class CreateBookingRequest:
    student_id: EntityId
    listing_id: EntityId
    idempotency_key: str


class CreateBooking(Protocol):
    async def execute(self, request: CreateBookingRequest) -> Booking:
        ...


@dataclass(frozen=True, slots=True)
class ConfirmBookingRequest:
    booking_id: EntityId
    caller_id: EntityId


class ConfirmBooking(Protocol):
    async def execute(self, request: ConfirmBookingRequest) -> None:
        ...


@dataclass(frozen=True, slots=True)
class ExpireHoldsResponse:
    expired_count: int


class ExpireHolds(Protocol):
    async def execute(self) -> ExpireHoldsResponse:
        ...


@dataclass(frozen=True, slots=True)
class CancelBookingRequest:
    booking_id: EntityId
    caller_id: EntityId
    cancellation_reason: str


class CancelBooking(Protocol):
    async def execute(self, request: CancelBookingRequest) -> None:
        ...


@dataclass(frozen=True, slots=True)
class GetBookingRequest:
    booking_id: EntityId
    caller_id: EntityId


class GetBooking(Protocol):
    async def execute(self, request: GetBookingRequest) -> Booking:
        ...


@dataclass(frozen=True, slots=True)
class ListMyBookingsRequest:
    caller_id: EntityId
    page: PageRequest


class ListMyBookings(Protocol):
    async def execute(self, request: ListMyBookingsRequest) -> Page[Booking]:
        ...


@dataclass(frozen=True, slots=True)
class ListBookingsForPropertyRequest:
    property_id: EntityId
    caller_id: EntityId
    page: PageRequest


class ListBookingsForProperty(Protocol):
    async def execute(self, request: ListBookingsForPropertyRequest) -> Page[Booking]:
        ...


@dataclass(frozen=True, slots=True)
class ConfirmHandoverOfferedRequest:
    booking_id: EntityId
    caller_id: EntityId


class ConfirmHandoverOffered(Protocol):
    async def execute(self, request: ConfirmHandoverOfferedRequest) -> None:
        ...


@dataclass(frozen=True, slots=True)
class ConfirmHandoverAcceptedRequest:
    booking_id: EntityId
    caller_id: EntityId


class ConfirmHandoverAccepted(Protocol):
    async def execute(self, request: ConfirmHandoverAcceptedRequest) -> None:
        ...
