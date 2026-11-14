"""Identity module domain entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from camp_match.modules.identity.domain.value_objects import (
    AccountStatus,
    EmailVerificationSource,
    ExternalProvider,
    OneTimeCodePurpose,
)
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from camp_match.modules.identity.domain.value_objects import EmailAddress

IdentityId = EntityId


@dataclass
class UserAccount:
    """Represents a user's security identity and account lifecycle."""

    id: IdentityId
    email: EmailAddress
    password_hash: str | None
    status: AccountStatus
    created_at: datetime
    email_verified_at: datetime | None = None
    email_verification_source: EmailVerificationSource | None = None

    def __post_init__(self) -> None:
        has_at = self.email_verified_at is not None
        has_src = self.email_verification_source is not None
        if has_at != has_src:
            raise ValueError(
                "email_verified_at and email_verification_source must be both set or both null."
            )

    @classmethod
    def register(
        cls,
        id: IdentityId,
        email: EmailAddress,
        password_hash: str,
        created_at: datetime,
    ) -> UserAccount:
        """Constructs a pre-verified account in the ACTIVE state (backward compatible)."""
        return cls(
            id=id,
            email=email,
            password_hash=password_hash,
            status=AccountStatus.ACTIVE,
            created_at=created_at,
            email_verified_at=created_at,
            email_verification_source=EmailVerificationSource.LEGACY,
        )

    @classmethod
    def register_unverified(
        cls,
        id: IdentityId,
        email: EmailAddress,
        password_hash: str,
        created_at: datetime,
    ) -> UserAccount:
        """Constructs an unverified account with a password."""
        return cls(
            id=id,
            email=email,
            password_hash=password_hash,
            status=AccountStatus.ACTIVE,
            created_at=created_at,
            email_verified_at=None,
            email_verification_source=None,
        )

    @classmethod
    def register_verified(
        cls,
        id: IdentityId,
        email: EmailAddress,
        password_hash: str,
        created_at: datetime,
        source: EmailVerificationSource,
    ) -> UserAccount:
        """Constructs a pre-verified account with a password (e.g. legacy)."""
        return cls(
            id=id,
            email=email,
            password_hash=password_hash,
            status=AccountStatus.ACTIVE,
            created_at=created_at,
            email_verified_at=created_at,
            email_verification_source=source,
        )

    @classmethod
    def register_with_google(
        cls,
        id: IdentityId,
        email: EmailAddress,
        created_at: datetime,
    ) -> UserAccount:
        """Constructs a verified Google-authenticated account without a password."""
        return cls(
            id=id,
            email=email,
            password_hash=None,
            status=AccountStatus.ACTIVE,
            created_at=created_at,
            email_verified_at=created_at,
            email_verification_source=EmailVerificationSource.GOOGLE,
        )

    @property
    def is_email_verified(self) -> bool:
        """Returns True if the email address has been verified."""
        return self.email_verified_at is not None

    @property
    def has_password(self) -> bool:
        """Returns True if the account has a password set."""
        return self.password_hash is not None

    def mark_email_verified(self, now: datetime, source: EmailVerificationSource) -> bool:
        """Idempotently marks the email as verified. Returns True if newly verified."""
        if self.is_email_verified:
            return False
        self.email_verified_at = now
        self.email_verification_source = source
        return True

    def replace_unverified_credentials(self, new_password_hash: str) -> None:
        """Replaces credentials for an unverified account. Raises if already verified."""
        if self.is_email_verified:
            raise ValueError("Cannot replace credentials on a verified account.")
        self.password_hash = new_password_hash

    def claim_for_google(self, now: datetime) -> None:
        """Claims an unverified account for Google sign-in (clears password, verifies)."""
        if self.is_email_verified:
            raise ValueError("Cannot claim an already verified account with Google.")
        self.password_hash = None
        self.email_verified_at = now
        self.email_verification_source = EmailVerificationSource.GOOGLE

    def set_password(self, new_password_hash: str) -> None:
        """Sets a password on a passwordless account. Raises if password already exists."""
        if self.has_password:
            raise ValueError("Account already has a password.")
        self.password_hash = new_password_hash

    def suspend(self) -> None:
        """Transitions the account to SUSPENDED state."""
        self.status = AccountStatus.SUSPENDED

    def disable(self) -> None:
        """Transitions the account to DISABLED state."""
        self.status = AccountStatus.DISABLED

    def reactivate(self) -> None:
        """Transitions the account back to ACTIVE state."""
        self.status = AccountStatus.ACTIVE

    @property
    def can_authenticate(self) -> bool:
        """Returns True if the account is allowed to authenticate right now."""
        return self.status == AccountStatus.ACTIVE


@dataclass(frozen=True)
class ExternalIdentity:
    """Represents an external federated identity (e.g. Google)."""

    id: EntityId
    account_id: EntityId
    provider: ExternalProvider
    subject: str
    email_at_link: str
    linked_at: datetime
    last_login_at: datetime | None = None


@dataclass
class OneTimeCode:
    """Represents a time-bounded one-time code for email verification or password reset."""

    id: EntityId
    account_id: EntityId
    purpose: OneTimeCodePurpose
    code_hash: str
    issued_at: datetime
    expires_at: datetime
    max_attempts: int
    attempts: int = 0
    consumed_at: datetime | None = None
    invalidated_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        """Returns True if the code is not consumed, not invalidated, and not expired."""
        return self.consumed_at is None and self.invalidated_at is None and now < self.expires_at

    def register_failed_attempt(self, now: datetime) -> int:
        """Increments attempts. Invalidates if max_attempts reached. Returns remaining attempts."""
        self.attempts += 1
        remaining = max(0, self.max_attempts - self.attempts)
        if self.attempts >= self.max_attempts:
            self.invalidated_at = now
        return remaining

    def consume(self, now: datetime) -> None:
        """Consumes the one-time code idempotently."""
        if self.consumed_at is None:
            self.consumed_at = now

    def invalidate(self, now: datetime) -> None:
        """Invalidates the one-time code idempotently."""
        if self.invalidated_at is None:
            self.invalidated_at = now
