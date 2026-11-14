"""Set password use case."""

from __future__ import annotations

import structlog

from camp_match.modules.identity.application.errors import (
    IdentityNotFound,
    PasswordAlreadySet,
)
from camp_match.modules.identity.application.ports.inbound import SetPasswordRequest
from camp_match.modules.identity.application.ports.outbound import (
    IdentityRepository,
    PasswordHasher,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class SetPasswordUseCase:
    def __init__(
        self,
        identity_repo: IdentityRepository,
        password_hasher: PasswordHasher,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._identity_repo = identity_repo
        self._password_hasher = password_hasher
        self._unit_of_work = unit_of_work

    async def execute(self, request: SetPasswordRequest) -> None:
        try:
            account_id = EntityId.from_string(request.identity_id)
        except ValueError as e:
            raise IdentityNotFound(f"Invalid identifier format: {e}") from e

        account = await self._identity_repo.get_by_id(account_id)
        if account is None:
            raise IdentityNotFound("Account not found.")

        if account.has_password:
            raise PasswordAlreadySet("This account already has a password.")

        hashed = self._password_hasher.hash(request.raw_password)
        account.set_password(hashed)

        async with self._unit_of_work:
            await self._identity_repo.update(account)
            await self._unit_of_work.commit()

        logger.info("password_set_on_account", identity_id=str(account_id))
