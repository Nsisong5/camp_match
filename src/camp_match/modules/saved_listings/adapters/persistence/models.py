"""Saved listings SQLAlchemy models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from camp_match.platform.db.base import Base


class SavedListingModel(Base):
    __tablename__ = "saved_listings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    listing_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "listing_id", name="uq_saved_listings_user_listing"
        ),
    )
