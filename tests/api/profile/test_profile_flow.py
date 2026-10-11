import pytest
from httpx import AsyncClient
from camp_match.modules.security.domain.value_objects import Role
from camp_match.modules.security.adapters.persistence.repository import SqlAlchemyRoleRepository
from camp_match.shared_kernel.domain.identifiers import EntityId


@pytest.mark.api
@pytest.mark.asyncio
async def test_profile_university_response_shapes(client: AsyncClient, db_session):
    # Setup admin to create a university
    reg_admin = await client.post("/api/v1/auth/register", json={"email": "admin_uni@example.com", "password": "password123"})
    admin_id = reg_admin.json()["id"]
    role_repo = SqlAlchemyRoleRepository(db_session)
    await role_repo.assign_role(EntityId.from_string(admin_id), Role.ADMIN)
    await db_session.commit()

    login_admin = await client.post("/api/v1/auth/login", json={"email": "admin_uni@example.com", "password": "password123"})
    admin_headers = {"Authorization": f"Bearer {login_admin.json()['access_token']}"}

    uni_resp = await client.post("/api/v1/universities", json={"official_name": "Uni Lagos", "institution_type": "UNIVERSITY", "state_region": "Lagos"}, headers=admin_headers)
    print("UNI RESP:", uni_resp.json())
    uni_id = uni_resp.json()["id"]

    # Student 2: Canonical state (university_id set)
    await client.post("/api/v1/auth/register", json={"email": "student2@example.com", "password": "password123"})
    h2 = {"Authorization": f"Bearer {(await client.post('/api/v1/auth/login', json={'email': 'student2@example.com', 'password': 'password123'})).json()['access_token']}"}
    await client.post("/api/v1/profiles", headers=h2, json={"display_name": "S2", "profile_type": "STUDENT"})
    up2 = await client.patch("/api/v1/profiles/me/student", headers=h2, json={"university_id": uni_id})
    print("UP2 RESP:", up2.status_code, up2.json())
    assert up2.status_code == 200
