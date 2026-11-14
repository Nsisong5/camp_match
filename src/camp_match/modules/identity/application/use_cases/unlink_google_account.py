"""Unlink Google account use case."""

from __future__ import annotations

import structlog

from camp_match.modules.identity.application.errors import (
    IdentityNotFound,
    LastSignInMethod,
)
from camp_match.modules.identity.application.ports.inbound import UnlinkGoogleRequest
from camp_match.modules.identity.application.ports.outbound import (
    ExternalIdentityRepository,
    IdentityRepository,
)
from camp_match.modules.identity.domain.value_objects import ExternalProvider
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class UnlinkGoogleAccountUseCase:
    def __init__(
        self,
        identity_repo: IdentityRepository,
        external_identity_repo: ExternalIdentityRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._identity_repo = identity_repo
        self._external_identity_repo = external_identity_repo
        self._unit_of_work = unit_of_work

    async def execute(self, request: UnlinkGoogleRequest) -> None:
        try:
            account_id = EntityId.from_string(request.identity_id)
        except ValueError as e:
            raise IdentityNotFound(f"Invalid identifier format: {e}") from e

        account = await self._identity_repo.get_by_id(account_id)
        if account is None:
            raise IdentityNotFound("Account not found.")

        provider = ExternalProvider.GOOGLE
        existing_links = await self._external_identity_repo.get_by_account(account_id, provider)
        if not existing_links:
            # No link -> succeed as no-op
            return

        # Check if account has password
        if not account.has_password:
            raise LastSignInMethod("You need at least one way to sign in. Set a password first.")

        async with self._unit_of_work:
            await self._external_identity_repo.remove(account_id, provider)
            await self._unit_of_work.commit()

        logger.info("google_account_unlinked", identity_id=str(account_id))
