"""Resend email verification use case."""

from __future__ import annotations

import structlog

from camp_match.modules.identity.application.ports.inbound import ResendVerificationRequest
from camp_match.modules.identity.application.ports.outbound import IdentityRepository
from camp_match.modules.identity.application.services.email_verification_issuer import (
    EmailVerificationIssuer,
)
from camp_match.modules.identity.domain.value_objects import AccountStatus, EmailAddress

logger = structlog.get_logger()


class ResendEmailVerificationUseCase:
    def __init__(
        self,
        identity_repo: IdentityRepository,
        issuer: EmailVerificationIssuer,
    ) -> None:
        self._identity_repo = identity_repo
        self._issuer = issuer

    async def execute(self, request: ResendVerificationRequest) -> None:
        email_addr = EmailAddress(request.email.strip().lower())
        account = await self._identity_repo.get_by_email(email_addr)

        if not account:
            logger.info("resend_verification_skipped", reason="no_account")
            return

        if account.status != AccountStatus.ACTIVE:
            logger.info(
                "resend_verification_skipped",
                reason="account_not_active",
                account_id=str(account.id),
            )
            return

        if account.is_email_verified:
            logger.info(
                "resend_verification_skipped",
                reason="already_verified",
                account_id=str(account.id),
            )
            return

        outcome = await self._issuer.issue_and_send(account)
        logger.info(
            "resend_verification_finished",
            outcome=outcome,
            account_id=str(account.id),
        )
