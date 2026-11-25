from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from camp_match.platform.db.base import Base

class PayoutAccountModel(Base):
    __tablename__ = "payout_accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    scout_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    bank_code: Mapped[str] = mapped_column(String, nullable=False)
    last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    release_hold_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'REPLACED')", name="check_payout_account_status"),
        Index("ix_payout_accounts_active_scout", "scout_id", postgresql_where=text("status = 'ACTIVE'"), unique=True),
    )
