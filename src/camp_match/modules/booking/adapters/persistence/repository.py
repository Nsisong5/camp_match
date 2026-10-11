from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError

from camp_match.modules.booking.adapters.persistence.models import BookingModel
from camp_match.modules.booking.domain.entities import Booking
from camp_match.modules.booking.domain.value_objects import (
    BillingPeriod,
    BookingStatus,
    Currency,
    PriceSnapshot,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyBookingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, booking: Booking) -> Booking:
        model = BookingModel(
            id=booking.id.value,
            student_id=booking.student_id.value,
            listing_id=booking.listing_id.value,
            unit_id=booking.unit_id.value,
            property_id=booking.property_id.value,
            status=booking.status.value,
            price_amount_kobo=booking.price.amount_kobo,
            price_currency=booking.price.currency.value,
            price_period=booking.price.period.value,
            verification_confirmed_at_booking=booking.verification_confirmed_at_booking,
            idempotency_key=booking.idempotency_key,
            expires_at=booking.expires_at,
            created_at=booking.created_at,
            confirmed_at=booking.confirmed_at,
            cancelled_at=booking.cancelled_at,
            cancelled_by=booking.cancelled_by.value if booking.cancelled_by else None,
            cancellation_reason=booking.cancellation_reason,
        )
        try:
            self._session.add(model)
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            existing = await self.get_by_idempotency_key(booking.student_id, booking.idempotency_key)
            if existing:
                return existing
            raise
        return booking

    async def get_by_id(self, booking_id: EntityId) -> Booking | None:
        stmt = select(BookingModel).where(BookingModel.id == booking_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_idempotency_key(
        self, student_id: EntityId, idempotency_key: str
    ) -> Booking | None:
        stmt = select(BookingModel).where(
            BookingModel.student_id == student_id.value,
            BookingModel.idempotency_key == idempotency_key,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_by_student(
        self, student_id: EntityId, page: PageRequest
    ) -> Page[Booking]:
        stmt = select(BookingModel).where(BookingModel.student_id == student_id.value).order_by(BookingModel.created_at.desc())

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self._session.execute(count_stmt)
        total = total_res.scalar_one()

        offset = (page.page - 1) * page.page_size
        stmt = stmt.offset(offset).limit(page.page_size)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        items = [self._to_domain(m) for m in models]
        return Page(items=items, total=total, page=page.page, page_size=page.page_size)

    async def find_by_property(
        self, property_id: EntityId, page: PageRequest
    ) -> Page[Booking]:
        stmt = select(BookingModel).where(BookingModel.property_id == property_id.value).order_by(BookingModel.created_at.desc())

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self._session.execute(count_stmt)
        total = total_res.scalar_one()

        offset = (page.page - 1) * page.page_size
        stmt = stmt.offset(offset).limit(page.page_size)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        items = [self._to_domain(m) for m in models]
        return Page(items=items, total=total, page=page.page, page_size=page.page_size)

    async def find_expired_holds(self, as_of: datetime) -> list[Booking]:
        stmt = select(BookingModel).where(
            BookingModel.status == BookingStatus.AWAITING_PAYMENT.value,
            BookingModel.expires_at < as_of,
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def confirm(self, booking_id: EntityId, confirmed_at: datetime) -> bool:
        stmt = (
            update(BookingModel)
            .where(
                BookingModel.id == booking_id.value,
                BookingModel.status == BookingStatus.AWAITING_PAYMENT.value,
            )
            .values(status=BookingStatus.CONFIRMED.value, confirmed_at=confirmed_at)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def cancel(
        self,
        booking_id: EntityId,
        cancelled_at: datetime,
        cancelled_by: EntityId,
        cancellation_reason: str,
    ) -> bool:
        stmt = (
            update(BookingModel)
            .where(
                BookingModel.id == booking_id.value,
                BookingModel.status.in_([
                    BookingStatus.AWAITING_PAYMENT.value,
                    BookingStatus.CONFIRMED.value,
                ]),
            )
            .values(
                status=BookingStatus.CANCELLED.value,
                cancelled_at=cancelled_at,
                cancelled_by=cancelled_by.value,
                cancellation_reason=cancellation_reason,
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def expire(self, booking_id: EntityId) -> bool:
        stmt = (
            update(BookingModel)
            .where(
                BookingModel.id == booking_id.value,
                BookingModel.status == BookingStatus.AWAITING_PAYMENT.value,
            )
            .values(status=BookingStatus.EXPIRED.value)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    def _to_domain(self, model: BookingModel) -> Booking:
        return Booking(
            id=EntityId(model.id),
            student_id=EntityId(model.student_id),
            listing_id=EntityId(model.listing_id),
            unit_id=EntityId(model.unit_id),
            property_id=EntityId(model.property_id),
            status=BookingStatus(model.status),
            price=PriceSnapshot(
                amount_kobo=model.price_amount_kobo,
                currency=Currency(model.price_currency),
                period=BillingPeriod(model.price_period),
            ),
            verification_confirmed_at_booking=model.verification_confirmed_at_booking,
            idempotency_key=model.idempotency_key,
            expires_at=model.expires_at,
            created_at=model.created_at,
            confirmed_at=model.confirmed_at,
            cancelled_at=model.cancelled_at,
            cancelled_by=EntityId(model.cancelled_by) if model.cancelled_by else None,
            cancellation_reason=model.cancellation_reason,
        )
