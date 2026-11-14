"""Use case for authenticating a user and issuing tokens."""

from __future__ import annotations

import contextlib

import structlog

from camp_match.config.settings import Settings
from camp_match.modules.identity.application.errors import (
    AccountDisabled,
    AccountSuspended,
    EmailNotVerified,
    InvalidCredentials,
)
from camp_match.modules.identity.application.ports.inbound import (
    AuthenticationRequest,
    TokenResponse,
)
from camp_match.modules.identity.application.ports.outbound import (
    AuthenticationSessionPort,
    IdentityRepository,
    PasswordHasher,
)
from camp_match.modules.identity.application.services.email_verification_issuer import (
    EmailVerificationIssuer,
)
from camp_match.modules.identity.domain.value_objects import AccountStatus, EmailAddress

logger = structlog.get_logger()


class AuthenticateUserUseCase:
    def __init__(
        self,
        repository: IdentityRepository,
        password_hasher: PasswordHasher,
        session_port: AuthenticationSessionPort,
        issuer: EmailVerificationIssuer | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._session_port = session_port
        self._issuer = issuer
        self._settings = settings

    async def execute(self, request: AuthenticationRequest) -> TokenResponse:
        try:
            email_vo = EmailAddress(request.email)
        except ValueError:
            logger.warning("login_failed", reason="invalid_email_format")
            raise InvalidCredentials("Invalid credentials.") from None

        account = await self._repository.get_by_email(email_vo)

        if account is None:
            logger.warning("login_failed", reason="account_not_found", email=str(email_vo))
            raise InvalidCredentials("Invalid credentials.")

        if account.password_hash is None:
            logger.warning("login_failed", reason="account_has_no_password", email=str(email_vo))
            raise InvalidCredentials("Invalid credentials.")

        is_valid = self._password_hasher.verify(request.raw_password, account.password_hash)
        if not is_valid:
            logger.warning("login_failed", reason="invalid_password", identity_id=str(account.id))
            raise InvalidCredentials("Invalid credentials.")

        if not account.can_authenticate:
            logger.warning("login_blocked", status=account.status.name, identity_id=str(account.id))
            if account.status == AccountStatus.SUSPENDED:
                raise AccountSuspended("Account is suspended.")
            elif account.status == AccountStatus.DISABLED:
                raise AccountDisabled("Account is disabled.")
            else:
                raise InvalidCredentials("Account cannot authenticate.")

        verification_required = (
            self._settings.identity_email_verification_required
            if self._settings is not None
            else False
        )
        if verification_required and not account.is_email_verified:
            logger.warning("login_blocked_unverified", identity_id=str(account.id))
            if self._issuer is not None:
                with contextlib.suppress(Exception):
                    await self._issuer.issue_and_send(account)
            raise EmailNotVerified("Your email address has not been verified.")

        token_pair = await self._session_port.issue_tokens(account.id)

        logger.info("login_succeeded", identity_id=str(account.id))

        return TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type=token_pair.token_type,
            expires_in=token_pair.expires_in,
        )
