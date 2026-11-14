"""Outbound ports for the Identity module, defining repository, hashing, and token interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from camp_match.modules.identity.domain.entities import (
        ExternalIdentity,
        OneTimeCode,
        UserAccount,
    )
    from camp_match.modules.identity.domain.value_objects import (
        EmailAddress,
        ExternalProvider,
        OneTimeCodePurpose,
    )
    from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str


@dataclass(frozen=True)
class VerifiedGoogleIdentity:
    subject: str
    email: str
    email_verified: bool
    hosted_domain: str | None


class IdentityRepository(Protocol):
    async def add(self, account: UserAccount) -> None:
        """Persists a new user account."""
        ...

    async def get_by_email(self, email: EmailAddress) -> UserAccount | None:
        """Retrieves a user account by email address."""
        ...

    async def get_by_id(self, identity_id: EntityId) -> UserAccount | None:
        """Retrieves a user account by its entity ID."""
        ...

    async def update(self, account: UserAccount) -> None:
        """Persists state updates to an existing account."""
        ...


class ExternalIdentityRepository(Protocol):
    async def get_by_subject(
        self, provider: ExternalProvider, subject: str
    ) -> ExternalIdentity | None: ...

    async def get_by_account(
        self, account_id: EntityId, provider: ExternalProvider
    ) -> list[ExternalIdentity]: ...

    async def add(self, identity: ExternalIdentity) -> None: ...

    async def remove(self, account_id: EntityId, provider: ExternalProvider) -> bool: ...

    async def touch_last_login(self, identity_id: EntityId, now: datetime) -> None: ...

    async def list_methods(self, account_id: EntityId) -> list[str]: ...


class OneTimeCodeRepository(Protocol):
    async def get_active(
        self, account_id: EntityId, purpose: OneTimeCodePurpose
    ) -> OneTimeCode | None: ...

    async def add_replacing_active(self, code: OneTimeCode) -> None: ...

    async def update(self, code: OneTimeCode) -> None: ...

    async def count_issued_since(
        self, account_id: EntityId, purpose: OneTimeCodePurpose, since: datetime
    ) -> int: ...

    async def latest_issued_at(
        self, account_id: EntityId, purpose: OneTimeCodePurpose
    ) -> datetime | None: ...

    async def invalidate_all(
        self, account_id: EntityId, purpose: OneTimeCodePurpose, now: datetime
    ) -> None: ...


class OneTimeCodeService(Protocol):
    def generate(self) -> str: ...

    def hash(self, account_id: EntityId, purpose: OneTimeCodePurpose, code: str) -> str: ...

    def matches(
        self,
        account_id: EntityId,
        purpose: OneTimeCodePurpose,
        code: str,
        code_hash: str,
    ) -> bool: ...


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class GoogleIdentityVerifier(Protocol):
    async def verify(self, id_token: str, nonce: str | None) -> VerifiedGoogleIdentity: ...


class PasswordHasher(Protocol):
    def hash(self, raw_password: str) -> str:
        """Hashes a raw password into a secure string."""
        ...

    def verify(self, raw_password: str, encoded_hash: str) -> bool:
        """Verifies a raw password against an encoded hash."""
        ...


class AuthenticationSessionPort(Protocol):
    async def issue_tokens(self, identity_id: EntityId) -> TokenPair:
        """Issues a new token pair for the given identity."""
        ...

    async def refresh(self, refresh_token: str) -> TokenPair:
        """Refreshes a token pair using a valid, unrevoked refresh token."""
        ...

    async def revoke(self, refresh_token: str) -> None:
        """
        Revokes a refresh token, rendering it invalid for future refreshes.
        Must be idempotent.
        """
        ...

    async def decode_access_token(self, access_token: str) -> EntityId:
        """
        Decodes an access token and returns the encapsulated EntityId.
        Raises InvalidCredentials if invalid or expired.
        """
        ...
