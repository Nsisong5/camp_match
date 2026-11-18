from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_tasks_rbac_and_validation(client: AsyncClient, scout_user: tuple[str, str], admin_user: tuple[str, str], operations_user: tuple[str, str]) -> None:
    scout_token, _ = scout_user
    admin_token, _ = admin_user
    ops_token, _ = operations_user

    # 1. Scout/student cannot access admin tasks (403 or 401)
    resp = await client.get("/api/v1/admin/tasks", headers={"Authorization": f"Bearer {scout_token}"})
    assert resp.status_code in [403, 401]

    # 2. Admin can access admin tasks
    resp = await client.get("/api/v1/admin/tasks", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "as_of" in data
    assert "sections" in data

    # 3. Operations can access admin tasks
    resp = await client.get("/api/v1/admin/tasks", headers={"Authorization": f"Bearer {ops_token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_tasks_limit_bounds_validation(client: AsyncClient, admin_user: tuple[str, str]) -> None:
    admin_token, _ = admin_user

    # limit_per_source = 0 -> 422 validation error
    resp = await client.get("/api/v1/admin/tasks?limit_per_source=0", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 422

    # limit_per_source = 101 -> 422 validation error
    resp = await client.get("/api/v1/admin/tasks?limit_per_source=101", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 422

    # limit_per_source = 50 -> 200 OK
    resp = await client.get("/api/v1/admin/tasks?limit_per_source=50", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
