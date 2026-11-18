from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest

from camp_match.modules.booking.application.errors import (
    BookingNotConfirmedForHandover,
    BookingNotFound,
    HandoverNotOffered,
)
from camp_match.modules.booking.application.ports.inbound import (
    ConfirmHandoverAcceptedRequest,
    ConfirmHandoverOfferedRequest,
)
from camp_match.modules.booking.application.use_cases.confirm_handover_accepted import (
    ConfirmHandoverAcceptedUseCase,
)
from camp_match.modules.booking.application.use_cases.confirm_handover_offered import (
    ConfirmHandoverOfferedUseCase,
)
from camp_match.modules.booking.domain.entities import Booking
from camp_match.modules.booking.domain.events import HandoverAccepted, HandoverOffered
from camp_match.modules.booking.domain.value_objects import (
    BillingPeriod,
    BookingStatus,
    Currency,
    PriceSnapshot,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.errors import ForbiddenError
from camp_match.shared_kernel.domain.identifiers import EntityId
from tests.support.fixed_clock import FixedClock


class FakeBookingRepository:
    def __init__(self, booking: Booking) -> None:
        self.booking = booking

    async def get_by_id(self, booking_id: EntityId) -> Booking | None:
        if self.booking.id == booking_id:
            return self.booking
        return None

    async def confirm_handover_offered(
        self, booking_id: EntityId, offered_at: datetime, offered_by: EntityId
    ) -> bool:
        if self.booking.id == booking_id and self.booking.handover_offered_at is None:
            self.booking.handover_offered_at = offered_at
            self.booking.handover_offered_by = offered_by
            return True
        return False

    async def confirm_handover_accepted(
        self, booking_id: EntityId, accepted_at: datetime
    ) -> bool:
        if (
            self.booking.id == booking_id
            and self.booking.handover_offered_at is not None
            and self.booking.handover_accepted_at is None
        ):
            self.booking.handover_accepted_at = accepted_at
            return True
        return False


class FakeHousingProvider:
    def __init__(self, owner_id: EntityId) -> None:
        self.owner_id = owner_id

    async def get_property_owner(self, property_id: EntityId) -> EntityId:
        return self.owner_id


class FakeAuthorizationService:
    def __init__(self, authorized_ids: set[EntityId]) -> None:
        self.authorized_ids = authorized_ids

    async def authorize(
        self, caller_id: EntityId, permission: Permission, resource_owner_id: EntityId | None = None
    ) -> None:
        if caller_id not in self.authorized_ids:
            raise ForbiddenError("Forbidden")


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        pass

    def add_event(self, event: object) -> None:
        self.events.append(event)

    async def commit(self) -> None:
        pass


def _create_booking(
    status: BookingStatus = BookingStatus.CONFIRMED,
    handover_offered_at: datetime | None = None,
    handover_accepted_at: datetime | None = None,
) -> tuple[Booking, EntityId, EntityId, EntityId]:
    clock_now = datetime.now(UTC)
    student_id = EntityId.new()
    provider_id = EntityId.new()
    booking_id = EntityId.new()

    booking = Booking(
        id=booking_id,
        student_id=student_id,
        listing_id=EntityId.new(),
        unit_id=EntityId.new(),
        property_id=EntityId.new(),
        status=status,
        price=PriceSnapshot(
            amount_kobo=15000000,
            currency=Currency.NGN,
            period=BillingPeriod.YEAR,
        ),
        verification_confirmed_at_booking=True,
        idempotency_key="key-test",
        expires_at=clock_now + timedelta(days=1),
        created_at=clock_now,
        confirmed_at=clock_now if status == BookingStatus.CONFIRMED else None,
        handover_offered_at=handover_offered_at,
        handover_offered_by=provider_id if handover_offered_at else None,
        handover_accepted_at=handover_accepted_at,
    )
    return booking, booking_id, student_id, provider_id


@pytest.mark.anyio
async def test_accept_before_offer_rejected_handover_not_offered() -> None:
    booking, booking_id, student_id, provider_id = _create_booking(status=BookingStatus.CONFIRMED)
    repo = FakeBookingRepository(booking)
    uow = FakeUnitOfWork()
    clock = FixedClock(datetime.now(UTC))

    use_case = ConfirmHandoverAcceptedUseCase(booking_repo=repo, uow=uow, clock=clock)

    with pytest.raises(HandoverNotOffered) as exc_info:
        await use_case.execute(ConfirmHandoverAcceptedRequest(booking_id=booking_id, caller_id=student_id))

    assert exc_info.value.code == "handover_not_offered"
    assert booking.handover_accepted_at is None
    assert len(uow.events) == 0


@pytest.mark.anyio
async def test_offer_then_accept_success_order_verified() -> None:
    t0 = datetime.now(UTC)
    clock = FixedClock(t0)
    booking, booking_id, student_id, provider_id = _create_booking(status=BookingStatus.CONFIRMED)
    repo = FakeBookingRepository(booking)
    uow = FakeUnitOfWork()
    housing = FakeHousingProvider(provider_id)
    auth = FakeAuthorizationService({provider_id})

    offer_uc = ConfirmHandoverOfferedUseCase(repo, housing, auth, uow, clock)
    await offer_uc.execute(ConfirmHandoverOfferedRequest(booking_id=booking_id, caller_id=provider_id))

    assert booking.handover_offered_at == t0
    assert booking.handover_offered_by == provider_id
    assert len(uow.events) == 1
    assert isinstance(uow.events[0], HandoverOffered)

    # Fast forward clock 1 hour
    clock.advance(3600)
    t1 = clock.now()

    accept_uc = ConfirmHandoverAcceptedUseCase(repo, uow, clock)
    await accept_uc.execute(ConfirmHandoverAcceptedRequest(booking_id=booking_id, caller_id=student_id))

    assert booking.handover_accepted_at == t1
    assert booking.handover_accepted_at >= booking.handover_offered_at
    assert len(uow.events) == 2
    assert isinstance(uow.events[1], HandoverAccepted)


@pytest.mark.anyio
async def test_offer_on_awaiting_payment_rejected() -> None:
    clock = FixedClock(datetime.now(UTC))
    booking, booking_id, student_id, provider_id = _create_booking(status=BookingStatus.AWAITING_PAYMENT)
    repo = FakeBookingRepository(booking)
    uow = FakeUnitOfWork()
    housing = FakeHousingProvider(provider_id)
    auth = FakeAuthorizationService({provider_id})

    offer_uc = ConfirmHandoverOfferedUseCase(repo, housing, auth, uow, clock)
    with pytest.raises(BookingNotConfirmedForHandover) as exc_info:
        await offer_uc.execute(ConfirmHandoverOfferedRequest(booking_id=booking_id, caller_id=provider_id))

    assert exc_info.value.code == "booking_not_confirmed_for_handover"
    assert booking.handover_offered_at is None
    assert len(uow.events) == 0


@pytest.mark.anyio
async def test_accept_on_cancelled_or_expired_rejected() -> None:
    clock = FixedClock(datetime.now(UTC))

    for status in (BookingStatus.CANCELLED, BookingStatus.EXPIRED):
        booking, booking_id, student_id, provider_id = _create_booking(
            status=status,
            handover_offered_at=clock.now() - timedelta(hours=2),
        )
        repo = FakeBookingRepository(booking)
        uow = FakeUnitOfWork()

        accept_uc = ConfirmHandoverAcceptedUseCase(repo, uow, clock)
        with pytest.raises(BookingNotConfirmedForHandover) as exc_info:
            await accept_uc.execute(ConfirmHandoverAcceptedRequest(booking_id=booking_id, caller_id=student_id))

        assert exc_info.value.code == "booking_not_confirmed_for_handover"
        assert booking.handover_accepted_at is None
        assert len(uow.events) == 0


@pytest.mark.anyio
async def test_idempotent_repeats_no_second_event() -> None:
    t0 = datetime.now(UTC)
    clock = FixedClock(t0)
    booking, booking_id, student_id, provider_id = _create_booking(status=BookingStatus.CONFIRMED)
    repo = FakeBookingRepository(booking)
    uow = FakeUnitOfWork()
    housing = FakeHousingProvider(provider_id)
    auth = FakeAuthorizationService({provider_id})

    offer_uc = ConfirmHandoverOfferedUseCase(repo, housing, auth, uow, clock)
    await offer_uc.execute(ConfirmHandoverOfferedRequest(booking_id=booking_id, caller_id=provider_id))
    assert len(uow.events) == 1

    # Repeat offer
    await offer_uc.execute(ConfirmHandoverOfferedRequest(booking_id=booking_id, caller_id=provider_id))
    assert len(uow.events) == 1  # No second event

    accept_uc = ConfirmHandoverAcceptedUseCase(repo, uow, clock)
    await accept_uc.execute(ConfirmHandoverAcceptedRequest(booking_id=booking_id, caller_id=student_id))
    assert len(uow.events) == 2

    # Repeat accept
    await accept_uc.execute(ConfirmHandoverAcceptedRequest(booking_id=booking_id, caller_id=student_id))
    assert len(uow.events) == 2  # No third event


@pytest.mark.anyio
async def test_wrong_actor_rejected_forbidden() -> None:
    clock = FixedClock(datetime.now(UTC))
    booking, booking_id, student_id, provider_id = _create_booking(status=BookingStatus.CONFIRMED)
    repo = FakeBookingRepository(booking)
    uow = FakeUnitOfWork()
    housing = FakeHousingProvider(provider_id)
    auth = FakeAuthorizationService({provider_id})

    stranger_id = EntityId.new()

    offer_uc = ConfirmHandoverOfferedUseCase(repo, housing, auth, uow, clock)
    with pytest.raises(ForbiddenError):
        await offer_uc.execute(ConfirmHandoverOfferedRequest(booking_id=booking_id, caller_id=stranger_id))

    # Set offered
    booking.handover_offered_at = clock.now()
    booking.handover_offered_by = provider_id

    accept_uc = ConfirmHandoverAcceptedUseCase(repo, uow, clock)
    with pytest.raises(ForbiddenError):
        await accept_uc.execute(ConfirmHandoverAcceptedRequest(booking_id=booking_id, caller_id=stranger_id))
