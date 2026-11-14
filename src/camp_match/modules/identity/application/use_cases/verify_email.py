"""Verify email use case."""

from __future__ import annotations

import structlog

from camp_match.modules.identity.application.errors import InvalidOrExpiredCode
from camp_match.modules.identity.application.ports.inbound import (
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from camp_match.modules.identity.application.ports.outbound import (
    IdentityRepository,
    OneTimeCodeRepository,
    OneTimeCodeService,
)
from camp_match.modules.identity.domain.value_objects import (
    EmailAddress,
    EmailVerificationSource,
    OneTimeCodePurpose,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock

logger = structlog.get_logger()


class VerifyEmailUseCase:
    def __init__(
        self,
        identity_repo: IdentityRepository,
        otc_repo: OneTimeCodeRepository,
        otc_service: OneTimeCodeService,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._identity_repo = identity_repo
        self._otc_repo = otc_repo
        self._otc_service = otc_service
        self._clock = clock
        self._uow = uow

    async def execute(self, request: VerifyEmailRequest) -> VerifyEmailResponse:
        now = self._clock.now()
        email_addr = EmailAddress(request.email.strip().lower())
        purpose = OneTimeCodePurpose.EMAIL_VERIFICATION

        account = await self._identity_repo.get_by_email(email_addr)
        if not account:
            logger.warning("email_verification_failed", reason="no_account")
            raise InvalidOrExpiredCode()

        if account.is_email_verified:
            logger.warning(
                "email_verification_failed",
                reason="already_verified",
                account_id=str(account.id),
            )
            raise InvalidOrExpiredCode()

        otc = await self._otc_repo.get_active(account.id, purpose)
        if not otc:
            logger.warning(
                "email_verification_failed",
                reason="no_active_code",
                account_id=str(account.id),
            )
            raise InvalidOrExpiredCode()

        if not otc.is_active(now):
            logger.warning(
                "email_verification_failed",
                reason="expired",
                account_id=str(account.id),
            )
            raise InvalidOrExpiredCode()

        if not self._otc_service.matches(account.id, purpose, request.code, otc.code_hash):
            reason = "locked" if otc.attempts + 1 >= otc.max_attempts else "wrong_code"
            otc.register_failed_attempt(now)
            async with self._uow:
                await self._otc_repo.update(otc)
                await self._uow.commit()

            logger.warning(
                "email_verification_failed",
                reason=reason,
                account_id=str(account.id),
            )
            raise InvalidOrExpiredCode()

        otc.consume(now)
        account.mark_email_verified(now, EmailVerificationSource.OTP)

        async with self._uow:
            await self._otc_repo.update(otc)
            await self._identity_repo.update(account)
            await self._uow.commit()

        logger.info("email_verified", account_id=str(account.id))
        return VerifyEmailResponse(verified=True)
