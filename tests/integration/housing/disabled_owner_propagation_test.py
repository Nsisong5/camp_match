from __future__ import annotations

import pytest
from camp_match.modules.housing.adapters.persistence.repository import (
    SqlAlchemyListingRepository,
    SqlAlchemyPropertyRepository,
    SqlAlchemyUnitRepository,
)
from camp_match.modules.housing.application.use_cases.disabled_owner_suspension import (
    SuspendListingsForDisabledOwnerUseCase,
    LiftOwnerAccountSuspensionsUseCase,
)
from camp_match.modules.housing.domain.value_objects import (
    BillingPeriod,
    Coordinates,
    Currency,
    ListingStatus,
    Price,
    PropertyType,
)
from camp_match.modules.housing.domain.entities import Listing, Property, Unit
from camp_match.modules.identity.domain.events import AccountDisabled, AccountReactivated
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId


@pytest.mark.anyio
async def test_disabled_owner_propagation_flow(db_session, session_factory) -> None:
    owner_id = EntityId.new()

    # Create property, units, and listings for owner
    prop_repo = SqlAlchemyPropertyRepository(db_session)
    unit_repo = SqlAlchemyUnitRepository(db_session)
    listing_repo = SqlAlchemyListingRepository(db_session)
    uow = SqlAlchemyUnitOfWork(db_session)

    prop = Property(
        id=EntityId.new(),
        provider_id=owner_id,
        property_type=PropertyType.LODGE,
        name="Owner Property",
        description=None,
        address="123 Road",
        coordinates=Coordinates(latitude=6.0, longitude=3.0),
        campus_id=None,
    )
    await prop_repo.add(prop)

    unit1 = Unit(id=EntityId.new(), property_id=prop.id, label="U1", total_capacity=2)
    unit2 = Unit(id=EntityId.new(), property_id=prop.id, label="U2", total_capacity=2)
    unit3 = Unit(id=EntityId.new(), property_id=prop.id, label="U3", total_capacity=2)
    unit4 = Unit(id=EntityId.new(), property_id=prop.id, label="U4", total_capacity=2)
    await unit_repo.add(unit1)
    await unit_repo.add(unit2)
    await unit_repo.add(unit3)
    await unit_repo.add(unit4)
    await uow.commit()

    # 1. PUBLISHED listing
    l_pub = Listing(
        id=EntityId.new(),
        property_id=prop.id,
        unit_id=unit1.id,
        title="Published Listing",
        description=None,
        price=Price(amount_kobo=1000, currency=Currency.NGN, period=BillingPeriod.MONTH),
        status=ListingStatus.PUBLISHED,
    )
    # 2. UNAVAILABLE listing
    l_unavail = Listing(
        id=EntityId.new(),
        property_id=prop.id,
        unit_id=unit2.id,
        title="Unavailable Listing",
        description=None,
        price=Price(amount_kobo=1000, currency=Currency.NGN, period=BillingPeriod.MONTH),
        status=ListingStatus.UNAVAILABLE,
    )
    # 3. DRAFT listing
    l_draft = Listing(
        id=EntityId.new(),
        property_id=prop.id,
        unit_id=unit3.id,
        title="Draft Listing",
        description=None,
        price=Price(amount_kobo=1000, currency=Currency.NGN, period=BillingPeriod.MONTH),
        status=ListingStatus.DRAFT,
    )
    # 4. Safety suspended listing
    l_safety = Listing(
        id=EntityId.new(),
        property_id=prop.id,
        unit_id=unit4.id,
        title="Safety Suspended Listing",
        description=None,
        price=Price(amount_kobo=1000, currency=Currency.NGN, period=BillingPeriod.MONTH),
        status=ListingStatus.SUSPENDED,
        suspension_reason="SAFETY_ENFORCEMENT",
        suspension_reference=EntityId.new(),
    )

    await listing_repo.add(l_pub)
    await listing_repo.add(l_unavail)
    await listing_repo.add(l_draft)
    await listing_repo.add(l_safety)
    await uow.commit()

    # Trigger AccountDisabled
    suspend_uc = SuspendListingsForDisabledOwnerUseCase(session_factory, type("Settings", (), {"housing_owner_suspension_batch_size": 10})())
    await suspend_uc(owner_id, EntityId.new())

    # Verify results
    async with session_factory() as session:
        r = SqlAlchemyListingRepository(session)
        updated_pub = await r.get_by_id(l_pub.id)
        updated_unavail = await r.get_by_id(l_unavail.id)
        updated_draft = await r.get_by_id(l_draft.id)
        updated_safety = await r.get_by_id(l_safety.id)

    assert updated_pub.status == ListingStatus.SUSPENDED
    assert updated_pub.suspension_reason == "OWNER_ACCOUNT_DISABLED"
    assert updated_pub.suspension_reference == owner_id

    assert updated_unavail.status == ListingStatus.SUSPENDED
    assert updated_unavail.suspension_reason == "OWNER_ACCOUNT_DISABLED"
    assert updated_unavail.suspension_reference == owner_id

    assert updated_draft.status == ListingStatus.DRAFT  # untouched
    assert updated_safety.suspension_reason == "SAFETY_ENFORCEMENT"  # left untouched

    # Replay AccountDisabled (idempotency)
    await suspend_uc(owner_id, EntityId.new())

    # Trigger AccountReactivated
    reactivate_uc = LiftOwnerAccountSuspensionsUseCase(session_factory, type("Settings", (), {"housing_owner_suspension_batch_size": 10})())
    await reactivate_uc(owner_id, EntityId.new())

    async with session_factory() as session:
        r = SqlAlchemyListingRepository(session)
        react_pub = await r.get_by_id(l_pub.id)
        react_unavail = await r.get_by_id(l_unavail.id)
        react_safety = await r.get_by_id(l_safety.id)

    assert react_pub.status == ListingStatus.UNAVAILABLE  # never PUBLISHED directly
    assert react_pub.suspension_reason is None
    assert react_unavail.status == ListingStatus.UNAVAILABLE
    assert react_safety.suspension_reason == "SAFETY_ENFORCEMENT"  # safety remains suspended
