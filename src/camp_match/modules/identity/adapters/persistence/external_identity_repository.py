"""SQLAlchemy repository for external identities."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from camp_match.modules.identity.adapters.persistence.models import (
    AccountModel,
    ExternalIdentityModel,
)
from camp_match.modules.identity.application.errors import (
    GoogleAlreadyLinked,
    GoogleIdentityInUse,
)
from camp_match.modules.identity.domain.entities import ExternalIdentity
from camp_match.modules.identity.domain.value_objects import ExternalProvider
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyExternalIdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_subject(
        self, provider: ExternalProvider, subject: str
    ) -> ExternalIdentity | None:
        stmt = select(ExternalIdentityModel).where(
            ExternalIdentityModel.provider == provider.value,
            ExternalIdentityModel.subject == subject,
        )
        res = await self._session.execute(stmt)
        model = res.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_account(
        self, account_id: EntityId, provider: ExternalProvider
    ) -> list[ExternalIdentity]:
        stmt = select(ExternalIdentityModel).where(
            ExternalIdentityModel.account_id == account_id.value,
            ExternalIdentityModel.provider == provider.value,
        )
        res = await self._session.execute(stmt)
        models = res.scalars().all()
        return [self._to_domain(m) for m in models]

    async def add(self, identity: ExternalIdentity) -> None:
        model = ExternalIdentityModel(
            id=identity.id.value,
            account_id=identity.account_id.value,
            provider=identity.provider.value,
            subject=identity.subject,
            email_at_link=identity.email_at_link,
            linked_at=identity.linked_at,
            last_login_at=identity.last_login_at,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as e:
            err_str = str(e)
            if "provider" in err_str and "subject" in err_str:
                raise GoogleIdentityInUse(
                    "That Google account is linked to a different account."
                ) from e
            raise GoogleAlreadyLinked("A Google account is already linked.") from e

    async def remove(self, account_id: EntityId, provider: ExternalProvider) -> bool:
        stmt = delete(ExternalIdentityModel).where(
            ExternalIdentityModel.account_id == account_id.value,
            ExternalIdentityModel.provider == provider.value,
        )
        res = await self._session.execute(stmt)
        await self._session.flush()
        return (res.rowcount or 0) > 0  # type: ignore[attr-defined]

    async def touch_last_login(self, identity_id: EntityId, now: datetime) -> None:
        stmt = select(ExternalIdentityModel).where(ExternalIdentityModel.id == identity_id.value)
        res = await self._session.execute(stmt)
        model = res.scalar_one_or_none()
        if model:
            model.last_login_at = now
            await self._session.flush()

    async def list_methods(self, account_id: EntityId) -> list[str]:
        # Check password
        acc_stmt = select(AccountModel).where(AccountModel.id == account_id.value)
        acc_res = await self._session.execute(acc_stmt)
        acc = acc_res.scalar_one_or_none()
        methods: list[str] = []
        if acc and acc.password_hash is not None:
            methods.append("PASSWORD")

        ext_stmt = select(ExternalIdentityModel).where(
            ExternalIdentityModel.account_id == account_id.value
        )
        ext_res = await self._session.execute(ext_stmt)
        exts = ext_res.scalars().all()
        for ext in exts:
            if ext.provider not in methods:
                methods.append(ext.provider)
        return methods

    def _to_domain(self, model: ExternalIdentityModel) -> ExternalIdentity:
        return ExternalIdentity(
            id=EntityId(model.id),
            account_id=EntityId(model.account_id),
            provider=ExternalProvider(model.provider),
            subject=model.subject,
            email_at_link=model.email_at_link,
            linked_at=model.linked_at,
            last_login_at=model.last_login_at,
        )
