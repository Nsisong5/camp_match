"""Link Google account use case."""

from __future__ import annotations

import structlog

from camp_match.modules.identity.application.errors import (
    GoogleAlreadyLinked,
    IdentityNotFound,
)
from camp_match.modules.identity.application.ports.inbound import LinkGoogleRequest
from camp_match.modules.identity.application.ports.outbound import (
    ExternalIdentityRepository,
    GoogleIdentityVerifier,
    IdentityRepository,
)
from camp_match.modules.identity.domain.entities import ExternalIdentity
from camp_match.modules.identity.domain.value_objects import ExternalProvider
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class LinkGoogleAccountUseCase:
    def __init__(
        self,
        identity_repo: IdentityRepository,
        external_identity_repo: ExternalIdentityRepository,
        verifier: GoogleIdentityVerifier,
        clock: Clock,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._identity_repo = identity_repo
        self._external_identity_repo = external_identity_repo
        self._verifier = verifier
        self._clock = clock
        self._unit_of_work = unit_of_work

    async def execute(self, request: LinkGoogleRequest) -> None:
        try:
            account_id = EntityId.from_string(request.identity_id)
        except ValueError as e:
            raise IdentityNotFound(f"Invalid identifier format: {e}") from e

        account = await self._identity_repo.get_by_id(account_id)
        if account is None:
            raise IdentityNotFound("Account not found.")

        provider = ExternalProvider.GOOGLE
        existing_links = await self._external_identity_repo.get_by_account(account_id, provider)
        if existing_links:
            raise GoogleAlreadyLinked("A Google account is already linked.")

        verified = await self._verifier.verify(request.id_token, request.nonce)
        now = self._clock.now()

        ext_id = ExternalIdentity(
            id=EntityId.new(),
            account_id=account_id,
            provider=provider,
            subject=verified.subject,
            email_at_link=verified.email.strip().lower(),
            linked_at=now,
            last_login_at=now,
        )

        async with self._unit_of_work:
            await self._external_identity_repo.add(ext_id)
            await self._unit_of_work.commit()

        logger.info("google_account_linked", identity_id=str(account_id))
