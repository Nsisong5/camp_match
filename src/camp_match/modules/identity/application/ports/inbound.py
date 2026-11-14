"""Inbound ports for the Identity module defining use case interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class RegistrationRequest:
    email: str
    raw_password: str


@dataclass(frozen=True)
class RegistrationResponse:
    id: str
    email: str
    status: str
    created_at: datetime
    email_verification_required: bool = True


@dataclass(frozen=True)
class AuthenticationRequest:
    email: str
    raw_password: str


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


@dataclass(frozen=True)
class RefreshRequest:
    refresh_token: str


@dataclass(frozen=True)
class LogoutRequest:
    refresh_token: str


@dataclass(frozen=True)
class IdentityQueryRequest:
    identity_id: str


@dataclass(frozen=True)
class IdentityResponse:
    id: str
    email: str
    status: str
    created_at: datetime
    email_verified: bool = False
    sign_in_methods: list[str] = field(default_factory=lambda: ["PASSWORD"])


@dataclass(frozen=True)
class UpdateStatusRequest:
    identity_id: str


@dataclass(frozen=True)
class VerifyEmailRequest:
    email: str
    code: str


@dataclass(frozen=True)
class VerifyEmailResponse:
    verified: bool


@dataclass(frozen=True)
class ResendVerificationRequest:
    email: str


@dataclass(frozen=True)
class GoogleSignInRequest:
    id_token: str
    nonce: str | None = None


@dataclass(frozen=True)
class GoogleSignInResponse:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    is_new_account: bool


@dataclass(frozen=True)
class LinkGoogleRequest:
    identity_id: str
    id_token: str
    nonce: str | None = None


@dataclass(frozen=True)
class UnlinkGoogleRequest:
    identity_id: str


@dataclass(frozen=True)
class SetPasswordRequest:
    identity_id: str
    raw_password: str


@dataclass(frozen=True)
class GoogleSignInConfigResponse:
    enabled: bool
    real_enabled: bool
    mock_enabled: bool
    client_ids: list[str]


class RegisterAccount(Protocol):
    async def execute(self, request: RegistrationRequest) -> RegistrationResponse:
        """Register a new user account."""
        ...


class AuthenticateUser(Protocol):
    async def execute(self, request: AuthenticationRequest) -> TokenResponse:
        """Authenticate a user and return a token pair."""
        ...


class RefreshSession(Protocol):
    async def execute(self, request: RefreshRequest) -> TokenResponse:
        """Refresh an existing authentication session."""
        ...


class Logout(Protocol):
    async def execute(self, request: LogoutRequest) -> None:
        """Revoke the current authentication session."""
        ...


class GetIdentityById(Protocol):
    async def execute(self, request: IdentityQueryRequest) -> IdentityResponse:
        """Retrieve identity details by ID."""
        ...


class DisableAccount(Protocol):
    async def execute(self, request: UpdateStatusRequest) -> IdentityResponse:
        """Disable a user account."""
        ...


class ReactivateAccount(Protocol):
    async def execute(self, request: UpdateStatusRequest) -> IdentityResponse:
        """Reactivate a disabled user account."""
        ...


class VerifyEmail(Protocol):
    async def execute(self, request: VerifyEmailRequest) -> VerifyEmailResponse:
        """Verify an email address using a one-time code."""
        ...


class ResendEmailVerification(Protocol):
    async def execute(self, request: ResendVerificationRequest) -> None:
        """Resend an email verification one-time code."""
        ...


class SignInWithGoogle(Protocol):
    async def execute(self, request: GoogleSignInRequest) -> GoogleSignInResponse:
        """Sign in or sign up using a Google ID token."""
        ...


class LinkGoogleAccount(Protocol):
    async def execute(self, request: LinkGoogleRequest) -> None:
        """Link a Google account to an existing authenticated user."""
        ...


class UnlinkGoogleAccount(Protocol):
    async def execute(self, request: UnlinkGoogleRequest) -> None:
        """Unlink Google from an account."""
        ...


class SetPassword(Protocol):
    async def execute(self, request: SetPasswordRequest) -> None:
        """Set a password on a passwordless account."""
        ...


class GetGoogleSignInConfig(Protocol):
    async def execute(self) -> GoogleSignInConfigResponse:
        """Get public Google sign-in configuration."""
        ...
