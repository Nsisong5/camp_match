"""Use case for registering a new user account."""

from __future__ import annotations

import contextlib

import structlog

from camp_match.config.settings import Settings
from camp_match.modules.identity.application.errors import (
    IdentityAlreadyExists,
    InvalidAuthenticationRequest,
)
from camp_match.modules.identity.application.ports.inbound import (
    RegistrationRequest,
    RegistrationResponse,
)
from camp_match.modules.identity.application.ports.outbound import (
    IdentityRepository,
    OneTimeCodeRepository,
    PasswordHasher,
)
from camp_match.modules.identity.application.services.email_verification_issuer import (
    EmailVerificationIssuer,
)
from camp_match.modules.identity.domain.entities import UserAccount
from camp_match.modules.identity.domain.events import UserRegistered
from camp_match.modules.identity.domain.value_objects import (
    EmailAddress,
    EmailVerificationSource,
    OneTimeCodePurpose,
)
from camp_match.shared_kernel.application.event_bus import EventBus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class RegisterAccountUseCase:
    def __init__(
        self,
        repository: IdentityRepository,
        password_hasher: PasswordHasher,
        clock: Clock,
        event_bus: EventBus,
        unit_of_work: UnitOfWork,
        issuer: EmailVerificationIssuer | None = None,
        otc_repo: OneTimeCodeRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._clock = clock
        self._event_bus = event_bus
        self._unit_of_work = unit_of_work
        self._issuer = issuer
        self._otc_repo = otc_repo
        self._settings = settings

    async def execute(self, request: RegistrationRequest) -> RegistrationResponse:
        try:
            email_vo = EmailAddress(request.email)
        except ValueError as e:
            raise InvalidAuthenticationRequest(str(e)) from e

        verification_required = (
            self._settings.identity_email_verification_required
            if self._settings is not None
            else False
        )
        hashed_password = self._password_hasher.hash(request.raw_password)
        now = self._clock.now()

        existing = await self._repository.get_by_email(email_vo)
        if existing is not None:
            if existing.is_email_verified:
                logger.info("registration_rejected_duplicate", email=str(email_vo))
                raise IdentityAlreadyExists("Email is already registered.")
            else:
                existing.replace_unverified_credentials(hashed_password)
                if self._otc_repo is not None:
                    async with self._unit_of_work:
                        await self._otc_repo.invalidate_all(
                            existing.id, OneTimeCodePurpose.EMAIL_VERIFICATION, now
                        )
                        await self._repository.update(existing)
                        await self._unit_of_work.commit()
                else:
                    async with self._unit_of_work:
                        await self._repository.update(existing)
                        await self._unit_of_work.commit()

                if verification_required and self._issuer is not None:
                    with contextlib.suppress(Exception):
                        await self._issuer.issue_and_send(existing)

                logger.info(
                    "registration_unverified_credentials_replaced",
                    identity_id=str(existing.id),
                )
                return RegistrationResponse(
                    id=str(existing.id),
                    email=str(email_vo),
                    status=existing.status.name,
                    created_at=existing.created_at,
                    email_verification_required=verification_required
                    and not existing.is_email_verified,
                )

        account_id = EntityId.new()
        if verification_required:
            account = UserAccount.register_unverified(
                id=account_id,
                email=email_vo,
                password_hash=hashed_password,
                created_at=now,
            )
        else:
            account = UserAccount.register_verified(
                id=account_id,
                email=email_vo,
                password_hash=hashed_password,
                created_at=now,
                source=EmailVerificationSource.LEGACY,
            )

        async with self._unit_of_work:
            try:
                await self._repository.add(account)
                await self._unit_of_work.commit()
            except IdentityAlreadyExists as e:
                logger.info("registration_rejected_duplicate", email=str(email_vo))
                raise e

        event = UserRegistered(user_id=account_id, email=email_vo, occurred_at=now)
        await self._event_bus.publish(event)

        if verification_required and self._issuer is not None:
            with contextlib.suppress(Exception):
                await self._issuer.issue_and_send(account)

        logger.info(
            "registration_succeeded",
            identity_id=str(account_id),
            email=str(email_vo),
        )

        return RegistrationResponse(
            id=str(account_id),
            email=str(email_vo),
            status=account.status.name,
            created_at=account.created_at,
            email_verification_required=verification_required and not account.is_email_verified,
        )
