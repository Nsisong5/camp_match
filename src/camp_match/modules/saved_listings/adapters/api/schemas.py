"""Saved listings API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SaveListingResponseSchema(BaseModel):
    listing_id: str
    saved_at: datetime
    already_saved: bool


class SavedListingItemSchema(BaseModel):
    listing_id: str
    saved_at: datetime
    availability: str
    listing: dict[str, Any] | None = None


class SavedListingPageSchema(BaseModel):
    items: list[SavedListingItemSchema]
    total: int
    page: int
    page_size: int
