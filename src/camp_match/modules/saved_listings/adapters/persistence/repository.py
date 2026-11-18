"""Saved listings SQLAlchemy repository."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.modules.saved_listings.adapters.persistence.models import (
    SavedListingModel,
)
from camp_match.modules.saved_listings.application.errors import SavedLimitReached
from camp_match.modules.saved_listings.domain.entities import SavedListing
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class SqlAlchemySavedListingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, saved: SavedListing, max_per_user: int) -> bool:
        stmt = select(SavedListingModel).where(
            SavedListingModel.user_id == saved.user_id.value,
            SavedListingModel.listing_id == saved.listing_id.value,
        )
        res = await self._session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing is not None:
            return False

        count_stmt = (
            select(func.count())
            .select_from(SavedListingModel)
            .where(SavedListingModel.user_id == saved.user_id.value)
        )
        count_res = await self._session.execute(count_stmt)
        total_saves = count_res.scalar_one()
        if total_saves >= max_per_user:
            raise SavedLimitReached("Saved limit reached.")

        model = SavedListingModel(
            user_id=saved.user_id.value,
            listing_id=saved.listing_id.value,
            saved_at=saved.saved_at,
        )
        self._session.add(model)
        await self._session.commit()
        return True

    async def remove(self, user_id: EntityId, listing_id: EntityId) -> bool:
        stmt = delete(SavedListingModel).where(
            SavedListingModel.user_id == user_id.value,
            SavedListingModel.listing_id == listing_id.value,
        )
        res = await self._session.execute(stmt)
        await self._session.commit()
        return (res.rowcount or 0) > 0  # type: ignore[attr-defined]

    async def list_page(
        self, user_id: EntityId, page: PageRequest
    ) -> Page[SavedListing]:
        count_stmt = (
            select(func.count())
            .select_from(SavedListingModel)
            .where(SavedListingModel.user_id == user_id.value)
        )
        total_res = await self._session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = (
            select(SavedListingModel)
            .where(SavedListingModel.user_id == user_id.value)
            .order_by(
                SavedListingModel.saved_at.desc(),
                SavedListingModel.listing_id.asc(),
            )
            .offset((page.page - 1) * page.page_size)
            .limit(page.page_size)
        )
        res = await self._session.execute(stmt)
        models = res.scalars().all()
        items = [
            SavedListing(
                user_id=EntityId(m.user_id),
                listing_id=EntityId(m.listing_id),
                saved_at=m.saved_at,
            )
            for m in models
        ]
        return Page(
            items=items,
            total=total,
            page=page.page,
            page_size=page.page_size,
        )

    async def saved_among(
        self, user_id: EntityId, listing_ids: list[EntityId]
    ) -> set[EntityId]:
        if not listing_ids:
            return set()
        uuids = [lid.value for lid in listing_ids]
        stmt = select(SavedListingModel.listing_id).where(
            SavedListingModel.user_id == user_id.value,
            SavedListingModel.listing_id.in_(uuids),
        )
        res = await self._session.execute(stmt)
        rows = res.scalars().all()
        return {EntityId(r) for r in rows}

    async def get(
        self, user_id: EntityId, listing_id: EntityId
    ) -> SavedListing | None:
        stmt = select(SavedListingModel).where(
            SavedListingModel.user_id == user_id.value,
            SavedListingModel.listing_id == listing_id.value,
        )
        res = await self._session.execute(stmt)
        m = res.scalar_one_or_none()
        if not m:
            return None
        return SavedListing(
            user_id=EntityId(m.user_id),
            listing_id=EntityId(m.listing_id),
            saved_at=m.saved_at,
        )
