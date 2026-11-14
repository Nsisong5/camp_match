"""SQLAlchemy repository for one-time codes."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, delete, func, or_, select

from camp_match.modules.identity.adapters.persistence.models import OneTimeCodeModel
from camp_match.modules.identity.domain.entities import OneTimeCode
from camp_match.modules.identity.domain.value_objects import OneTimeCodePurpose
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyOneTimeCodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active(
        self, account_id: EntityId, purpose: OneTimeCodePurpose
    ) -> OneTimeCode | None:
        stmt = select(OneTimeCodeModel).where(
            OneTimeCodeModel.account_id == account_id.value,
            OneTimeCodeModel.purpose == purpose.value,
            OneTimeCodeModel.consumed_at.is_(None),
            OneTimeCodeModel.invalidated_at.is_(None),
        )
        res = await self._session.execute(stmt)
        model = res.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def add_replacing_active(self, code: OneTimeCode) -> None:
        await self.invalidate_all(code.account_id, code.purpose, code.issued_at)

        model = OneTimeCodeModel(
            id=code.id.value,
            account_id=code.account_id.value,
            purpose=code.purpose.value,
            code_hash=code.code_hash,
            issued_at=code.issued_at,
            expires_at=code.expires_at,
            attempts=code.attempts,
            max_attempts=code.max_attempts,
            consumed_at=code.consumed_at,
            invalidated_at=code.invalidated_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def update(self, code: OneTimeCode) -> None:
        stmt = select(OneTimeCodeModel).where(OneTimeCodeModel.id == code.id.value)
        res = await self._session.execute(stmt)
        model = res.scalar_one_or_none()
        if model:
            model.attempts = code.attempts
            model.consumed_at = code.consumed_at
            model.invalidated_at = code.invalidated_at
            await self._session.flush()

    async def count_issued_since(
        self, account_id: EntityId, purpose: OneTimeCodePurpose, since: datetime
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(OneTimeCodeModel)
            .where(
                OneTimeCodeModel.account_id == account_id.value,
                OneTimeCodeModel.purpose == purpose.value,
                OneTimeCodeModel.issued_at >= since,
            )
        )
        res = await self._session.execute(stmt)
        return res.scalar_one()

    async def latest_issued_at(
        self, account_id: EntityId, purpose: OneTimeCodePurpose
    ) -> datetime | None:
        stmt = select(func.max(OneTimeCodeModel.issued_at)).where(
            OneTimeCodeModel.account_id == account_id.value,
            OneTimeCodeModel.purpose == purpose.value,
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def invalidate_all(
        self, account_id: EntityId, purpose: OneTimeCodePurpose, now: datetime
    ) -> None:
        stmt = select(OneTimeCodeModel).where(
            OneTimeCodeModel.account_id == account_id.value,
            OneTimeCodeModel.purpose == purpose.value,
            OneTimeCodeModel.consumed_at.is_(None),
            OneTimeCodeModel.invalidated_at.is_(None),
        )
        res = await self._session.execute(stmt)
        models = res.scalars().all()
        for m in models:
            m.invalidated_at = now
        if models:
            await self._session.flush()

    async def purge_expired_or_inactive(self, cutoff: datetime, limit: int) -> int:
        subq = (
            select(OneTimeCodeModel.id)
            .where(
                or_(
                    and_(
                        OneTimeCodeModel.consumed_at.is_not(None),
                        OneTimeCodeModel.consumed_at < cutoff,
                    ),
                    and_(
                        OneTimeCodeModel.invalidated_at.is_not(None),
                        OneTimeCodeModel.invalidated_at < cutoff,
                    ),
                    OneTimeCodeModel.expires_at < cutoff,
                )
            )
            .limit(limit)
            .scalar_subquery()
        )
        stmt = delete(OneTimeCodeModel).where(OneTimeCodeModel.id.in_(subq))
        res = await self._session.execute(stmt)
        await self._session.flush()
        return int(res.rowcount)  # type: ignore[attr-defined]

    def _to_domain(self, model: OneTimeCodeModel) -> OneTimeCode:
        return OneTimeCode(
            id=EntityId(model.id),
            account_id=EntityId(model.account_id),
            purpose=OneTimeCodePurpose(model.purpose),
            code_hash=model.code_hash,
            issued_at=model.issued_at,
            expires_at=model.expires_at,
            max_attempts=model.max_attempts,
            attempts=model.attempts,
            consumed_at=model.consumed_at,
            invalidated_at=model.invalidated_at,
        )
