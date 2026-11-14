from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_listing_suspension_and_status_detail(
    client: AsyncClient,
    scout_token: str,
    student_token: str,
    admin_token: str,
    db_session,
) -> None:
    # 1. Create property as Scout
    prop_resp = await client.post(
        "/api/v1/properties",
        json={
            "property_type": "LODGE",
            "name": "Suspension Lodge",
            "address": "123 Campus Rd",
            "latitude": 6.5244,
            "longitude": 3.3792,
        },
        headers={"Authorization": f"Bearer {scout_token}"},
    )
    assert prop_resp.status_code == 201
    prop_id = prop_resp.json()["id"]

    # 2. Create unit
    unit_resp = await client.post(
        f"/api/v1/properties/{prop_id}/units",
        json={
            "label": "Room 101",
            "total_capacity": 2,
        },
        headers={"Authorization": f"Bearer {scout_token}"},
    )
    assert unit_resp.status_code == 201
    unit_id = unit_resp.json()["id"]

    # 3. Create listing
    listing_resp = await client.post(
        "/api/v1/listings",
        json={
            "property_id": prop_id,
            "unit_id": unit_id,
            "title": "Nice Room",
            "price_amount_kobo": 50000,
            "price_currency": "NGN",
            "price_period": "MONTH",
        },
        headers={"Authorization": f"Bearer {scout_token}"},
    )
    assert listing_resp.status_code == 201
    listing_id = listing_resp.json()["id"]

    # Publish listing
    pub_resp = await client.post(
        f"/api/v1/listings/{listing_id}/publish",
        headers={"Authorization": f"Bearer {scout_token}"},
    )
    assert pub_resp.status_code == 204

    # 4. Suspend listing via SuspendListingForSafetyUseCase
    from camp_match.modules.housing.adapters.persistence.repository import (
        SqlAlchemyListingRepository,
        SqlAlchemyPropertyRepository,
    )
    from camp_match.modules.housing.adapters.profile.profile_provider import (
        InProcessProfileProvider,
    )
    from camp_match.modules.housing.adapters.security.authorization import (
        InProcessAuthorizationService,
    )
    from camp_match.modules.housing.application.use_cases.unit_listing_management import (
        SuspendListingForSafetyCommand,
        SuspendListingForSafetyUseCase,
    )
    from camp_match.modules.profile.adapters.persistence.repository import (
        SqlAlchemyProfileRepository,
    )
    from camp_match.modules.profile.application.use_cases.get_current_user_profile import (
        GetCurrentUserProfileUseCase,
    )
    from camp_match.modules.security.adapters.persistence.repository import (
        SqlAlchemyRoleRepository,
    )
    from camp_match.modules.security.application.use_cases.authorize_action import (
        AuthorizeActionUseCase,
    )
    from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
    from camp_match.platform.security.authentication import (
        decode_access_token_string,
    )
    from camp_match.shared_kernel.domain.identifiers import EntityId

    listing_repo = SqlAlchemyListingRepository(db_session)
    prop_repo = SqlAlchemyPropertyRepository(db_session)
    role_repo = SqlAlchemyRoleRepository(db_session)
    profile_repo = SqlAlchemyProfileRepository(db_session)
    profile_uc = GetCurrentUserProfileUseCase(profile_repo)
    profile_provider = InProcessProfileProvider(profile_uc)
    auth_uc = AuthorizeActionUseCase(role_repo, profile_provider)
    auth = InProcessAuthorizationService(auth_uc)
    uow = SqlAlchemyUnitOfWork(db_session)

    admin_id = await decode_access_token_string(admin_token)

    suspend_uc = SuspendListingForSafetyUseCase(
        listing_repo, prop_repo, auth, uow, None
    )
    await suspend_uc(
        SuspendListingForSafetyCommand(
            identity_id=admin_id,
            listing_id=EntityId(listing_id),
            source_reference=EntityId.new(),
        )
    )

    # 5. Verify student gets 404 on GET /api/v1/listings/{listing_id}
    resp = await client.get(
        f"/api/v1/listings/{listing_id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp.status_code == 404

    # 6. Verify owner (scout) gets 200 with status_detail (SUSPENDED_SAFETY)
    resp = await client.get(
        f"/api/v1/listings/{listing_id}",
        headers={"Authorization": f"Bearer {scout_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUSPENDED"
    assert data["status_detail"]["code"] == "SUSPENDED_SAFETY"
    assert "safety review" in data["status_detail"]["message"]

    # 7. Verify admin gets 200
    resp = await client.get(
        f"/api/v1/listings/{listing_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
