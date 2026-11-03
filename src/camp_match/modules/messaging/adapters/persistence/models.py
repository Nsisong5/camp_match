from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from camp_match.platform.db.base import Base


class MessagingConversationModel(Base):
    __tablename__ = "messaging_conversations"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    context_type: Mapped[str] = mapped_column(String, nullable=False)
    listing_id: Mapped[UUID | None] = mapped_column(nullable=True)
    booking_id: Mapped[UUID | None] = mapped_column(nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    last_sequence: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("context_type IN ('LISTING', 'BOOKING')", name="check_messaging_conversation_context_type"),
        CheckConstraint("last_sequence >= 0", name="check_messaging_conversation_last_sequence"),
        CheckConstraint(
            "(context_type = 'LISTING' AND listing_id IS NOT NULL AND booking_id IS NULL) OR "
            "(context_type = 'BOOKING' AND booking_id IS NOT NULL AND listing_id IS NULL)",
            name="check_messaging_conversation_context_fields",
        ),
    )


class MessagingParticipantModel(Base):
    __tablename__ = "messaging_participants"

    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("messaging_conversations.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_read_sequence: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)
    last_read_message_id: Mapped[UUID | None] = mapped_column(nullable=True)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("last_read_sequence >= 0", name="check_messaging_participant_last_read_sequence"),
        Index("ix_messaging_participants_user_id", "user_id"),
    )


class MessagingMessageModel(Base):
    __tablename__ = "messaging_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("messaging_conversations.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    client_message_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence", name="uq_messaging_messages_conversation_sequence"),
        UniqueConstraint("sender_id", "client_message_id", name="uq_messaging_messages_sender_client_message_id"),
        ForeignKeyConstraint(
            ["conversation_id", "sender_id"],
            ["messaging_participants.conversation_id", "messaging_participants.user_id"],
            name="fk_messaging_messages_participant",
            ondelete="CASCADE",
        ),
        CheckConstraint("sequence >= 1", name="check_messaging_message_sequence"),
        CheckConstraint("char_length(content) BETWEEN 1 AND 10000", name="check_messaging_message_content_length"),
    )


class MessagingOutboxModel(Base):
    __tablename__ = "messaging_outbox"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_messaging_outbox_pending",
            "occurred_at",
            postgresql_where=text("dispatched_at IS NULL"),
        ),
    )


class MessagingRestrictionModel(Base):
    __tablename__ = "messaging_restrictions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_reference: Mapped[UUID] = mapped_column(nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE")
    lifted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'LIFTED')", name="check_messaging_restriction_status"),
        Index(
            "ix_messaging_restrictions_user_active",
            "user_id",
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )
