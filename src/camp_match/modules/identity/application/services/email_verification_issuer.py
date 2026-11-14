"""Email verification issuer service."""

from __future__ import annotations

from datetime import timedelta

import structlog

from camp_match.config.settings import Settings
from camp_match.modules.identity.application.ports.outbound import (
    EmailMessage,
    EmailSender,
    OneTimeCodeRepository,
    OneTimeCodeService,
)
from camp_match.modules.identity.domain.entities import OneTimeCode, UserAccount
from camp_match.modules.identity.domain.value_objects import OneTimeCodePurpose
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class EmailVerificationIssuer:
    def __init__(
        self,
        otc_repo: OneTimeCodeRepository,
        otc_service: OneTimeCodeService,
        email_sender: EmailSender,
        clock: Clock,
        uow: UnitOfWork,
        settings: Settings,
    ) -> None:
        self._otc_repo = otc_repo
        self._otc_service = otc_service
        self._email_sender = email_sender
        self._clock = clock
        self._uow = uow
        self._settings = settings

    async def issue_and_send(self, account: UserAccount) -> str:
        now = self._clock.now()
        purpose = OneTimeCodePurpose.EMAIL_VERIFICATION

        # 1. Cooldown and hourly cap check
        latest_issued = await self._otc_repo.latest_issued_at(account.id, purpose)
        cooldown_sec = self._settings.identity_otp_resend_cooldown_seconds
        if latest_issued and (now - latest_issued).total_seconds() < cooldown_sec:
            return "THROTTLED"

        one_hour_ago = now - timedelta(hours=1)
        count_recent = await self._otc_repo.count_issued_since(account.id, purpose, one_hour_ago)
        if count_recent >= self._settings.identity_otp_max_sends_per_hour:
            return "THROTTLED"

        # 2. Generate and store code
        code = self._otc_service.generate()
        code_hash = self._otc_service.hash(account.id, purpose, code)
        expires_at = now + timedelta(seconds=self._settings.identity_otp_ttl_seconds)

        otc = OneTimeCode(
            id=EntityId.new(),
            account_id=account.id,
            purpose=purpose,
            code_hash=code_hash,
            issued_at=now,
            expires_at=expires_at,
            max_attempts=self._settings.identity_otp_max_attempts,
        )

        async with self._uow:
            await self._otc_repo.add_replacing_active(otc)
            await self._uow.commit()

        logger.info("verification_code_issued", account_id=str(account.id))

        # 3. Send email after commit
        message = EmailMessage(
            to=account.email.value,
            subject="Verification Code",
            text=f"Your verification code is {code}",
        )
        try:
            await self._email_sender.send(message)
        except Exception as e:
            logger.error(
                "email_send_failed",
                account_id=str(account.id),
                error_type=e.__class__.__name__,
            )
            return "SEND_FAILED"

        return "SENT"
