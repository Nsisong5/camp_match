"""Module Messaging: restriction_management.py"""
from __future__ import annotations

from datetime import datetime, timezone

from camp_match.modules.messaging.adapters.persistence.repository import SqlAlchemyRestrictionRepository
from camp_match.modules.messaging.application.errors import RestrictionNotFound
from camp_match.modules.messaging.application.ports.inbound import (
    LiftCommunicationRestrictionRequest,
    RestrictCommunicationRequest,
)
from camp_match.modules.messaging.application.ports.outbound import AuthorizationService
from camp_match.modules.messaging.domain.entities import CommunicationRestriction
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.errors import ValidationError
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId


class RestrictCommunicationUseCase:
    def __init__(
        self,
        restriction_repo: SqlAlchemyRestrictionRepository,
        auth: AuthorizationService,
        uow: UnitOfWork,
    ) -> None:
        self._restriction_repo = restriction_repo
        self._auth = auth
        self._uow = uow

    async def execute(self, request: RestrictCommunicationRequest) -> None:
        await self._auth.authorize(request.actor_id, Permission.MESSAGING_RESTRICT)

        if request.ends_at <= datetime.now(timezone.utc):
            raise ValidationError("Restriction ends_at must be in the future.")

        existing = await self._restriction_repo.get_by_source_reference(request.source_reference)
        if existing:
            return  # Idempotent

        restriction = CommunicationRestriction(
            id=EntityId.new(),
            user_id=request.user_id,
            starts_at=datetime.now(timezone.utc),
            ends_at=request.ends_at,
            source_reference=request.source_reference,
            status="ACTIVE",
        )
        await self._restriction_repo.add(restriction)
        await self._uow.commit()


class LiftCommunicationRestrictionUseCase:
    def __init__(
        self,
        restriction_repo: SqlAlchemyRestrictionRepository,
        auth: AuthorizationService,
        uow: UnitOfWork,
    ) -> None:
        self._restriction_repo = restriction_repo
        self._auth = auth
        self._uow = uow

    async def execute(self, request: LiftCommunicationRestrictionRequest) -> None:
        await self._auth.authorize(request.actor_id, Permission.MESSAGING_RESTRICT)

        restriction = await self._restriction_repo.get_by_source_reference(request.source_reference)
        if not restriction:
            raise RestrictionNotFound("Restriction not found.")

        if restriction.status == "ACTIVE":
            restriction.status = "LIFTED"
            restriction.lifted_at = datetime.now(timezone.utc)
            await self._restriction_repo.update(restriction)
            await self._uow.commit()
