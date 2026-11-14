"""Sign in with Google use case."""

from __future__ import annotations

import structlog

from camp_match.modules.identity.application.errors import (
    AccountDisabled,
    AccountExistsUseExistingMethod,
    AccountSuspended,
    GoogleEmailNotSupported,
)
from camp_match.modules.identity.application.ports.inbound import (
    GoogleSignInRequest,
    GoogleSignInResponse,
)
from camp_match.modules.identity.application.ports.outbound import (
    AuthenticationSessionPort,
    ExternalIdentityRepository,
    GoogleIdentityVerifier,
    IdentityRepository,
    OneTimeCodeRepository,
)
from camp_match.modules.identity.domain.entities import ExternalIdentity, UserAccount
from camp_match.modules.identity.domain.events import UserRegistered
from camp_match.modules.identity.domain.value_objects import (
    AccountStatus,
    EmailAddress,
    ExternalProvider,
    OneTimeCodePurpose,
)
from camp_match.shared_kernel.application.event_bus import EventBus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class SignInWithGoogleUseCase:
    def __init__(
        self,
        identity_repo: IdentityRepository,
        external_identity_repo: ExternalIdentityRepository,
        otc_repo: OneTimeCodeRepository,
        verifier: GoogleIdentityVerifier,
        session_port: AuthenticationSessionPort,
        clock: Clock,
        event_bus: EventBus,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._identity_repo = identity_repo
        self._external_identity_repo = external_identity_repo
        self._otc_repo = otc_repo
        self._verifier = verifier
        self._session_port = session_port
        self._clock = clock
        self._event_bus = event_bus
        self._unit_of_work = unit_of_work

    async def execute(self, request: GoogleSignInRequest) -> GoogleSignInResponse:
        now = self._clock.now()
        provider = ExternalProvider.GOOGLE

        # 1. Verify token
        verified = await self._verifier.verify(request.id_token, request.nonce)

        for attempt in range(2):
            try:
                # 2. Check if external identity exists by subject
                ext_id = await self._external_identity_repo.get_by_subject(
                    provider, verified.subject
                )
                if ext_id is not None:
                    account = await self._identity_repo.get_by_id(ext_id.account_id)
                    if account is None:
                        # Orphaned external identity edge case
                        pass
                    else:
                        if not account.can_authenticate:
                            logger.warning(
                                "google_login_blocked",
                                status=account.status.name,
                                identity_id=str(account.id),
                            )
                            if account.status == AccountStatus.SUSPENDED:
                                raise AccountSuspended("Account is suspended.")
                            elif account.status == AccountStatus.DISABLED:
                                raise AccountDisabled("Account is disabled.")
                            else:
                                raise AccountSuspended("Account cannot authenticate.")

                        await self._external_identity_repo.touch_last_login(ext_id.id, now)
                        tokens = await self._session_port.issue_tokens(account.id)
                        logger.info(
                            "google_sign_in_succeeded",
                            identity_id=str(account.id),
                            is_new_account=False,
                        )
                        return GoogleSignInResponse(
                            access_token=tokens.access_token,
                            refresh_token=tokens.refresh_token,
                            token_type=tokens.token_type,
                            expires_in=tokens.expires_in,
                            is_new_account=False,
                        )

                # 3. Email validation rules for new link/account
                email_str = verified.email.strip().lower()
                is_gmail = email_str.endswith("@gmail.com") and email_str.count("@") == 1
                if not verified.email_verified or not (
                    is_gmail or verified.hosted_domain is not None
                ):
                    raise GoogleEmailNotSupported()

                email_vo = EmailAddress(email_str)

                # 4. Check existing account by email
                existing_account = await self._identity_repo.get_by_email(email_vo)
                if existing_account is not None:
                    if existing_account.status == AccountStatus.SUSPENDED:
                        raise AccountSuspended("Account is suspended.")
                    if existing_account.status == AccountStatus.DISABLED:
                        raise AccountDisabled("Account is disabled.")

                    if existing_account.is_email_verified:
                        logger.info(
                            "google_sign_in_existing_verified",
                            identity_id=str(existing_account.id),
                        )
                        raise AccountExistsUseExistingMethod()
                    else:
                        # Unverified account claim
                        existing_account.claim_for_google(now)
                        new_ext = ExternalIdentity(
                            id=EntityId.new(),
                            account_id=existing_account.id,
                            provider=provider,
                            subject=verified.subject,
                            email_at_link=email_str,
                            linked_at=now,
                            last_login_at=now,
                        )
                        async with self._unit_of_work:
                            await self._identity_repo.update(existing_account)
                            await self._external_identity_repo.add(new_ext)
                            await self._otc_repo.invalidate_all(
                                existing_account.id, OneTimeCodePurpose.EMAIL_VERIFICATION, now
                            )
                            await self._unit_of_work.commit()

                        logger.warning(
                            "unverified_account_claimed_by_google",
                            identity_id=str(existing_account.id),
                        )
                        tokens = await self._session_port.issue_tokens(existing_account.id)
                        logger.info(
                            "google_sign_in_succeeded",
                            identity_id=str(existing_account.id),
                            is_new_account=True,
                        )
                        return GoogleSignInResponse(
                            access_token=tokens.access_token,
                            refresh_token=tokens.refresh_token,
                            token_type=tokens.token_type,
                            expires_in=tokens.expires_in,
                            is_new_account=True,
                        )

                # Brand new account registration with Google
                new_account_id = EntityId.new()
                new_account = UserAccount.register_with_google(
                    id=new_account_id,
                    email=email_vo,
                    created_at=now,
                )
                new_ext = ExternalIdentity(
                    id=EntityId.new(),
                    account_id=new_account_id,
                    provider=provider,
                    subject=verified.subject,
                    email_at_link=email_str,
                    linked_at=now,
                    last_login_at=now,
                )

                async with self._unit_of_work:
                    await self._identity_repo.add(new_account)
                    await self._external_identity_repo.add(new_ext)
                    await self._unit_of_work.commit()

                event = UserRegistered(user_id=new_account_id, email=email_vo, occurred_at=now)
                await self._event_bus.publish(event)

                tokens = await self._session_port.issue_tokens(new_account_id)
                logger.info(
                    "google_sign_in_succeeded",
                    identity_id=str(new_account_id),
                    is_new_account=True,
                )
                return GoogleSignInResponse(
                    access_token=tokens.access_token,
                    refresh_token=tokens.refresh_token,
                    token_type=tokens.token_type,
                    expires_in=tokens.expires_in,
                    is_new_account=True,
                )

            except Exception:
                if attempt == 1:
                    raise
                # Retry once on potential race condition / unique violation
                continue

        raise RuntimeError("Unexpected flow in SignInWithGoogle")
