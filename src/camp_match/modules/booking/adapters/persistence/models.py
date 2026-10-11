from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    BigInteger,
    CheckConstraint,
    DateTime,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from camp_match.platform.db.base import Base


class BookingModel(Base):
    __tablename__ = "bookings"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    student_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    listing_id: Mapped[UUID] = mapped_column(nullable=False)
    unit_id: Mapped[UUID] = mapped_column(nullable=False)
    property_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    price_amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_currency: Mapped[str] = mapped_column(String, nullable=False)
    price_period: Mapped[str] = mapped_column(String, nullable=False)
    verification_confirmed_at_booking: Mapped[bool] = mapped_column(Boolean, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[UUID | None] = mapped_column(nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("student_id", "idempotency_key", name="uq_student_idempotency_key"),
        CheckConstraint(
            "status IN ('AWAITING_PAYMENT', 'CONFIRMED', 'CANCELLED', 'EXPIRED')",
            name="check_booking_status",
        ),
        CheckConstraint("price_amount_kobo >= 0", name="check_booking_price_non_negative"),
    )
