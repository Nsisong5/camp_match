from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4
import pytest
from httpx import AsyncClient
from sqlalchemy import text

from camp_match.modules.booking.adapters.persistence.models import BookingModel
from camp_match.modules.booking.domain.value_objects import BookingStatus
from camp_match.modules.housing.adapters.persistence.models import PropertyModel, UnitModel


async def create_user(client: AsyncClient, email: str, profile_type: str) -> tuple[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
    login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    token = login_resp.json()["access_token"]
    prof_resp = await client.post(
        "/api/v1/profiles",
        json={"display_name": email.split("@")[0], "profile_type": profile_type},
        headers={"Authorization": f"Bearer {token}"},
    )
    identity_id = prof_resp.json()["identity_id"]
    return token, identity_id


@pytest.mark.anyio
async def test_handover_ordered_api_workflow(client: AsyncClient, session_factory) -> None:
    # 1. Create Scout, Student, and Stranger
    scout_token, scout_id = await create_user(client, f"scout_{uuid4().hex[:8]}@example.com", "SCOUT")
    student_token, student_id = await create_user(client, f"student_{uuid4().hex[:8]}@example.com", "STUDENT")
    stranger_token, stranger_id = await create_user(client, f"stranger_{uuid4().hex[:8]}@example.com", "STUDENT")

    property_id = uuid4()
    unit_id = uuid4()
    booking_id = uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        # Create property owned by scout
        prop = PropertyModel(
            id=property_id,
            provider_id=uuid4() if scout_id is None else uuid4(), # placeholder, update to scout identity
        )
        prop.provider_id = uuid4() if not scout_id else uuid4()
        # Ensure property belongs to scout
        import uuid
        prop.provider_id = uuid.UUID(scout_id)
        prop.name = "Test Lodge"
        prop.property_type = "LODGE"
        prop.address = "1 University Way"
        prop.latitude = 6.5
        prop.longitude = 3.3
        prop.status = "ACTIVE"
        session.add(prop)

        # Create unit
        unit = UnitModel(
            id=unit_id,
            property_id=property_id,
            label="Room A",
            total_capacity=1,
            occupied_count=0,
        )
        session.add(unit)

        # Create booking in AWAITING_PAYMENT status
        booking = BookingModel(
            id=booking_id,
            student_id=uuid.UUID(student_id),
            listing_id=uuid4(),
            unit_id=unit_id,
            property_id=property_id,
            status=BookingStatus.AWAITING_PAYMENT.value,
            price_amount_kobo=10000000,
            price_currency="NGN",
            price_period="YEAR",
            verification_confirmed_at_booking=True,
            idempotency_key=f"idem-{uuid4().hex}",
            expires_at=now + timedelta(days=1),
            created_at=now,
        )
        session.add(booking)
        await session.commit()

    # Step 1: Offer on AWAITING_PAYMENT booking -> 409 booking_not_confirmed_for_handover
    resp = await client.post(
        f"/api/v1/bookings/{booking_id}/handover/offered",
        headers={"Authorization": f"Bearer {scout_token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "booking_not_confirmed_for_handover"

    # Step 2: Accept on AWAITING_PAYMENT booking -> 409 booking_not_confirmed_for_handover
    resp = await client.post(
        f"/api/v1/bookings/{booking_id}/handover/accepted",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "booking_not_confirmed_for_handover"

    # Transition booking to CONFIRMED
    async with session_factory() as session:
        await session.execute(
            text("UPDATE bookings SET status = 'CONFIRMED', confirmed_at = :now WHERE id = :id"),
            {"now": now, "id": booking_id},
        )
        await session.commit()

    # Step 3: Accept before offer on CONFIRMED booking -> 409 handover_not_offered
    resp = await client.post(
        f"/api/v1/bookings/{booking_id}/handover/accepted",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "handover_not_offered"

    # Step 4: Offer by wrong actor (student or stranger) -> 403 Forbidden
    resp = await client.post(
        f"/api/v1/bookings/{booking_id}/handover/offered",
        headers={"Authorization": f"Bearer {stranger_token}"},
    )
    assert resp.status_code == 403

    # Step 5: Offer by scout -> 204 No Content
    resp = await client.post(
        f"/api/v1/bookings/{booking_id}/handover/offered",
        headers={"Authorization": f"Bearer {scout_token}"},
    )
    assert resp.status_code == 204

    # Step 6: Repeat offer by scout -> 204 No Content (idempotent)
    resp = await client.post(
        f"/api/v1/bookings/{booking_id}/handover/offered",
        headers={"Authorization": f"Bearer {scout_token}"},
    )
    assert resp.status_code == 204

    # Step 7: Accept by wrong actor (stranger or scout) -> 403 Forbidden
    resp = await client.post(
        f"/api/v1/bookings/{booking_id}/handover/accepted",
        headers={"Authorization": f"Bearer {stranger_token}"},
    )
    assert resp.status_code == 403

    # Step 8: Accept by student -> 204 No Content
    resp = await client.post(
        f"/api/v1/bookings/{booking_id}/handover/accepted",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp.status_code == 204

    # Step 9: Repeat accept by student -> 204 No Content (idempotent)
    resp = await client.post(
        f"/api/v1/bookings/{booking_id}/handover/accepted",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp.status_code == 204

    # Step 10: Verify booking details
    resp = await client.get(
        f"/api/v1/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["handover_offered_at"] is not None
    assert data["handover_accepted_at"] is not None
    assert data["handover_accepted_at"] >= data["handover_offered_at"]
