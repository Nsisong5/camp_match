from __future__ import annotations

import pytest
from httpx import AsyncClient

from camp_match.modules.security.adapters.persistence.models import SecurityUserRoleModel
from camp_match.modules.security.domain.value_objects import Role
from camp_match.shared_kernel.domain.identifiers import EntityId


async def create_authenticated_user(client: AsyncClient, email: str, profile_type: str = "SCOUT") -> tuple[str, str]:
    await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "password123"
    })

    login_resp = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "password123"
    })
    token = login_resp.json()["access_token"]

    await client.post("/api/v1/profiles",
        json={
            "display_name": email.split("@")[0],
            "profile_type": profile_type
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    me_resp = await client.get("/api/v1/profiles/me", headers={"Authorization": f"Bearer {token}"})
    identity_id = me_resp.json()["identity_id"]

    return token, identity_id


@pytest.fixture
async def scout_user(client: AsyncClient) -> tuple[str, str]:
    return await create_authenticated_user(client, "admin_scout@example.com", "SCOUT")


@pytest.fixture
async def student_user(client: AsyncClient) -> tuple[str, str]:
    return await create_authenticated_user(client, "admin_student@example.com", "STUDENT")


@pytest.fixture
async def operations_user(client: AsyncClient, db_session) -> tuple[str, str]:
    token, identity_id = await create_authenticated_user(client, "admin_ops@example.com", "SCOUT")
    role_model = SecurityUserRoleModel(
        id=EntityId.new().value,
        identity_id=EntityId.from_string(identity_id).value,
        role=Role.OPERATIONS.name,
    )
    db_session.add(role_model)
    await db_session.commit()
    return token, identity_id


@pytest.fixture
async def admin_user(client: AsyncClient, db_session) -> tuple[str, str]:
    token, identity_id = await create_authenticated_user(client, "admin_root@example.com", "SCOUT")
    role_model = SecurityUserRoleModel(
        id=EntityId.new().value,
        identity_id=EntityId.from_string(identity_id).value,
        role=Role.ADMIN.name,
    )
    db_session.add(role_model)
    await db_session.commit()
    return token, identity_id
