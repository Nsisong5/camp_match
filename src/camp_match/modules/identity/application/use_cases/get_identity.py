"""Use case for retrieving identity details."""

from __future__ import annotations

import structlog

from camp_match.modules.identity.application.errors import IdentityNotFound
from camp_match.modules.identity.application.ports.inbound import (
    IdentityQueryRequest,
    IdentityResponse,
)
from camp_match.modules.identity.application.ports.outbound import (
    ExternalIdentityRepository,
    IdentityRepository,
)
from camp_match.modules.identity.domain.value_objects import EmailVerificationSource
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class GetIdentityByIdUseCase:
    def __init__(
        self,
        repository: IdentityRepository,
        external_identity_repository: ExternalIdentityRepository | None = None,
    ) -> None:
        self._repository = repository
        self._ext_repo = external_identity_repository

    async def execute(self, request: IdentityQueryRequest) -> IdentityResponse:
        try:
            entity_id = EntityId.from_string(request.identity_id)
        except ValueError as e:
            raise IdentityNotFound(f"Invalid identifier format: {e}") from e

        account = await self._repository.get_by_id(entity_id)
        if account is None:
            raise IdentityNotFound(f"No identity found with ID: {request.identity_id}")

        methods = ["PASSWORD"] if account.has_password else []
        if self._ext_repo is not None:
            ext_methods = await self._ext_repo.list_methods(account.id)
            for m in ext_methods:
                if m not in methods:
                    methods.append(m)
        elif not methods and account.email_verification_source == EmailVerificationSource.GOOGLE:
            methods = ["GOOGLE"]

        return IdentityResponse(
            id=str(account.id),
            email=str(account.email),
            status=account.status.name,
            created_at=account.created_at,
            email_verified=account.is_email_verified,
            sign_in_methods=methods,
        )
