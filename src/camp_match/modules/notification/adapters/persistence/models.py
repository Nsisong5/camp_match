"""Notification SQLAlchemy persistence models."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from camp_match.platform.db.base import Base


class NotificationModel(Base):
    __tablename__ = "notification_notifications"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    recipient_id: Mapped[UUID] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[UUID | None] = mapped_column(nullable=True)
    group_key: Mapped[str | None] = mapped_column(String, nullable=True)
    event_count: Mapped[int] = mapped_column(
        Integer, server_default=text("1"), nullable=False
    )
    source_event_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    latest_event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "source_event_id",
            "recipient_id",
            name="uq_notification_source_recipient",
        ),
        Index(
            "ix_notification_recipient_group_unread",
            "recipient_id",
            "group_key",
            unique=True,
            postgresql_where=text(
                "group_key IS NOT NULL AND read_at IS NULL"
            ),
        ),
        Index(
            "ix_notification_list",
            "recipient_id",
            text("latest_event_at DESC"),
            text("id DESC"),
        ),
        Index(
            "ix_notification_unread_recipient",
            "recipient_id",
            postgresql_where=text("read_at IS NULL"),
        ),
        CheckConstraint(
            "category IN ('MESSAGE', 'BOOKING', 'VERIFICATION')",
            name="check_notification_category",
        ),
        CheckConstraint(
            "type IN ("
            "'message.new', 'booking.created.provider', "
            "'booking.confirmed.student', 'booking.confirmed.provider', "
            "'booking.cancelled.student', 'booking.cancelled.provider', "
            "'booking.expired.student', 'verification.verified', "
            "'verification.rejected', 'verification.revoked'"
            ")",
            name="check_notification_type",
        ),
        CheckConstraint(
            "event_count >= 1", name="check_notification_event_count"
        ),
        CheckConstraint(
            "(target_type IS NULL AND target_id IS NULL) OR "
            "(target_type IS NOT NULL AND target_id IS NOT NULL)",
            name="check_notification_target_both",
        ),
        CheckConstraint(
            "target_type IS NULL OR target_type IN "
            "('CONVERSATION', 'BOOKING', 'VERIFICATION_CASE')",
            name="check_notification_target_type",
        ),
    )


class InboxModel(Base):
    __tablename__ = "notification_inbox"

    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String, server_default=text("'PENDING'"), nullable=False
    )
    attempts: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSED', 'REJECTED', 'DEAD')",
            name="check_notification_inbox_status",
        ),
        Index(
            "ix_notification_inbox_due",
            "next_attempt_at",
            postgresql_where=text("status = 'PENDING'"),
        ),
    )
