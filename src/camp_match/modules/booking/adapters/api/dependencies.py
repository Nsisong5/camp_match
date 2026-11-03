"""Booking API dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.config.settings import Settings, get_settings
from camp_match.modules.booking.adapters.housing.housing_provider import InProcessHousingProvider
from camp_match.modules.booking.adapters.persistence.repository import SqlAlchemyBookingRepository
from camp_match.modules.booking.adapters.security.authorization import InProcessAuthorizationService
from camp_match.modules.booking.adapters.verification.verification_provider import (
    InProcessVerificationProvider,
)
from camp_match.modules.booking.application.use_cases.cancel_booking import CancelBookingUseCase
from camp_match.modules.booking.application.use_cases.confirm_booking import ConfirmBookingUseCase
from camp_match.modules.booking.application.use_cases.confirm_handover_accepted import (
    ConfirmHandoverAcceptedUseCase,
)
from camp_match.modules.booking.application.use_cases.confirm_handover_offered import (
    ConfirmHandoverOfferedUseCase,
)
from camp_match.modules.booking.application.use_cases.create_booking import CreateBookingUseCase
from camp_match.modules.booking.application.use_cases.get_booking import GetBookingUseCase
from camp_match.modules.booking.application.use_cases.list_bookings_for_property import (
    ListBookingsForPropertyUseCase,
)
from camp_match.modules.booking.application.use_cases.list_my_bookings import ListMyBookingsUseCase
from camp_match.modules.housing.adapters.persistence.repository import (
    SqlAlchemyListingRepository,
    SqlAlchemyPropertyRepository,
    SqlAlchemyUnitRepository,
)
from camp_match.modules.profile.adapters.persistence.repository import SqlAlchemyProfileRepository
from camp_match.modules.profile.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from camp_match.modules.security.adapters.persistence.repository import SqlAlchemyRoleRepository
from camp_match.modules.security.adapters.profile.profile_provider import (
    InProcessProfileProvider as SecurityProfileProvider,
)
from camp_match.modules.security.application.use_cases.authorize_action import (
    AuthorizeActionUseCase,
)
from camp_match.modules.verification.adapters.persistence.repository import (
    SQLAlchemyVerificationCaseRepository,
    SQLAlchemyVerificationDecisionRepository,
)
from camp_match.modules.verification.application.use_cases.get_verification_status import (
    GetVerificationStatusUseCase,
)
from camp_match.platform.clock import SystemClock, get_clock
from camp_match.platform.db.session import get_db_session
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from camp_match.platform.event_bus import get_event_bus
from camp_match.shared_kernel.application.event_bus import EventBus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork


def get_uow(session: Annotated[AsyncSession, Depends(get_db_session)]) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(session)


def get_booking_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyBookingRepository:
    return SqlAlchemyBookingRepository(session)


def get_housing_provider(session: Annotated[AsyncSession, Depends(get_db_session)]) -> InProcessHousingProvider:
    listing_repo = SqlAlchemyListingRepository(session)
    property_repo = SqlAlchemyPropertyRepository(session)
    unit_repo = SqlAlchemyUnitRepository(session)
    return InProcessHousingProvider(listing_repo, property_repo, unit_repo)


def get_verification_provider(session: Annotated[AsyncSession, Depends(get_db_session)]) -> InProcessVerificationProvider:
    case_repo = SQLAlchemyVerificationCaseRepository(session)
    decision_repo = SQLAlchemyVerificationDecisionRepository(session)
    get_status_uc = GetVerificationStatusUseCase(case_repo, decision_repo)
    return InProcessVerificationProvider(get_status_uc)


def get_authorization_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> InProcessAuthorizationService:
    role_repo = SqlAlchemyRoleRepository(session)
    profile_repo = SqlAlchemyProfileRepository(session)
    profile_use_case = GetCurrentUserProfileUseCase(profile_repo)
    sec_profile_provider = SecurityProfileProvider(profile_use_case)
    authorize_uc = AuthorizeActionUseCase(role_repo, sec_profile_provider)
    return InProcessAuthorizationService(authorize_uc)


def get_create_booking_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    booking_repo: Annotated[SqlAlchemyBookingRepository, Depends(get_booking_repo)],
    housing_provider: Annotated[InProcessHousingProvider, Depends(get_housing_provider)],
    verification_provider: Annotated[InProcessVerificationProvider, Depends(get_verification_provider)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> CreateBookingUseCase:
    return CreateBookingUseCase(
        booking_repo, housing_provider, verification_provider, uow, clock, settings, event_bus
    )


def get_confirm_booking_use_case(
    booking_repo: Annotated[SqlAlchemyBookingRepository, Depends(get_booking_repo)],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> ConfirmBookingUseCase:
    return ConfirmBookingUseCase(booking_repo, auth_service, uow, clock, event_bus)


def get_cancel_booking_use_case(
    booking_repo: Annotated[SqlAlchemyBookingRepository, Depends(get_booking_repo)],
    housing_provider: Annotated[InProcessHousingProvider, Depends(get_housing_provider)],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> CancelBookingUseCase:
    return CancelBookingUseCase(booking_repo, housing_provider, auth_service, uow, clock, event_bus)


def get_get_booking_use_case(
    booking_repo: Annotated[SqlAlchemyBookingRepository, Depends(get_booking_repo)],
    housing_provider: Annotated[InProcessHousingProvider, Depends(get_housing_provider)],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
) -> GetBookingUseCase:
    return GetBookingUseCase(booking_repo, housing_provider, auth_service)


def get_list_my_bookings_use_case(
    booking_repo: Annotated[SqlAlchemyBookingRepository, Depends(get_booking_repo)],
) -> ListMyBookingsUseCase:
    return ListMyBookingsUseCase(booking_repo)


def get_list_bookings_for_property_use_case(
    booking_repo: Annotated[SqlAlchemyBookingRepository, Depends(get_booking_repo)],
    housing_provider: Annotated[InProcessHousingProvider, Depends(get_housing_provider)],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
) -> ListBookingsForPropertyUseCase:
    return ListBookingsForPropertyUseCase(booking_repo, housing_provider, auth_service)


def get_confirm_handover_offered_use_case(
    booking_repo: Annotated[SqlAlchemyBookingRepository, Depends(get_booking_repo)],
    housing_provider: Annotated[InProcessHousingProvider, Depends(get_housing_provider)],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
) -> ConfirmHandoverOfferedUseCase:
    return ConfirmHandoverOfferedUseCase(booking_repo, housing_provider, auth_service, uow, clock)


def get_confirm_handover_accepted_use_case(
    booking_repo: Annotated[SqlAlchemyBookingRepository, Depends(get_booking_repo)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
) -> ConfirmHandoverAcceptedUseCase:
    return ConfirmHandoverAcceptedUseCase(booking_repo, uow, clock)
