"""SQLAlchemy ORM models for the Identity module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from camp_match.platform.db.base import Base


class AccountModel(Base):
    """Database representation of a user account."""

    __tablename__ = "identity_accounts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'DISABLED')",
            name="check_account_status_valid",
        ),
        CheckConstraint(
            "email_verification_source IS NULL OR "
            "email_verification_source IN ('OTP', 'GOOGLE', 'LEGACY')",
            name="check_email_verification_source_valid",
        ),
        CheckConstraint(
            "(email_verified_at IS NULL) = (email_verification_source IS NULL)",
            name="check_email_verification_both_or_neither",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ACTIVE")

    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_verification_source: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )


class ExternalIdentityModel(Base):
    """Database representation of external federated identities."""

    __tablename__ = "identity_external_identities"
    __table_args__ = (
        CheckConstraint(
            "provider = 'GOOGLE'",
            name="check_external_identity_provider_valid",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email_at_link: Mapped[str] = mapped_column(String(254), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OneTimeCodeModel(Base):
    """Database representation of one-time verification/reset codes."""

    __tablename__ = "identity_one_time_codes"
    __table_args__ = (
        CheckConstraint(
            "purpose = 'EMAIL_VERIFICATION'",
            name="check_otp_purpose_valid",
        ),
        Index(
            "ix_identity_otp_account_purpose_issued",
            "account_id",
            "purpose",
            "issued_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RefreshTokenModel(Base):
    __tablename__ = "identity_refresh_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[UUID | None] = mapped_column(nullable=True)
