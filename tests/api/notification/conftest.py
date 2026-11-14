import pytest
from httpx import AsyncClient


async def create_authenticated_user(client: AsyncClient, email: str, profile_type: str) -> str:
    # 1. Register
    await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "password123"
    })
    
    # 2. Login
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    
    # 3. Create Profile
    await client.post("/api/v1/profiles", 
        json={
            "display_name": email.split("@")[0],
            "profile_type": profile_type
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    return token


@pytest.fixture
async def scout_token(client: AsyncClient) -> str:
    return await create_authenticated_user(client, "scout_notif@example.com", "SCOUT")


@pytest.fixture
async def student_token(client: AsyncClient) -> str:
    return await create_authenticated_user(client, "student_notif@example.com", "STUDENT")
