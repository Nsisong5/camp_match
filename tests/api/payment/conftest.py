import pytest
from httpx import AsyncClient


async def create_authenticated_user(client: AsyncClient, email: str, profile_type: str) -> str:
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
    
    return token


@pytest.fixture
async def student_token(client: AsyncClient) -> str:
    return await create_authenticated_user(client, "student_payment_test@example.com", "STUDENT")
