"""Saved listings inbound ports and DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True)
class SaveListingCommand:
    user_id: EntityId
    listing_id: EntityId


@dataclass(frozen=True)
class SaveListingResult:
    listing_id: EntityId
    saved_at: datetime
    already_saved: bool


class SaveListing(Protocol):
    async def execute(self, cmd: SaveListingCommand) -> SaveListingResult: ...


@dataclass(frozen=True)
class UnsaveListingCommand:
    user_id: EntityId
    listing_id: EntityId


class UnsaveListing(Protocol):
    async def execute(self, cmd: UnsaveListingCommand) -> None: ...


@dataclass(frozen=True)
class ListSavedListingsQuery:
    user_id: EntityId
    page_request: PageRequest


@dataclass(frozen=True)
class SavedListingItem:
    listing_id: EntityId
    saved_at: datetime
    availability: str  # "AVAILABLE" | "FULLY_BOOKED" | "UNAVAILABLE"
    listing: dict[str, Any] | None


class ListSavedListings(Protocol):
    async def execute(self, query: ListSavedListingsQuery) -> Page[SavedListingItem]: ...


@dataclass(frozen=True)
class GetSavedStateQuery:
    user_id: EntityId
    listing_ids: list[EntityId]


class GetSavedState(Protocol):
    async def execute(self, query: GetSavedStateQuery) -> set[EntityId]: ...
