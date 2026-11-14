"""Mock Google token minter router (local/test + mock mode only)."""

from __future__ import annotations

import hashlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from camp_match.config.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/dev/google-mock", tags=["google-mock"])


class MintTokenRequest(BaseModel):
    email: str
    email_verified: bool = True
    hosted_domain: str | None = None


@router.post("/token", response_model=dict[str, Any])
async def mint_mock_google_token(
    body: MintTokenRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    env = settings.app_env.lower()
    backend = settings.google_auth_backend.lower()
    mock_enabled = env in ("local", "test") and backend in ("fake", "both")

    if not mock_enabled:
        raise HTTPException(status_code=404, detail="Not found")

    email = body.email.strip().lower()
    sub = hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]

    parts = [f"fake:{email}:{sub}"]
    if not body.email_verified:
        parts.append("unverified")
    if body.hosted_domain:
        parts.append(f"hd={body.hosted_domain.strip().lower()}")

    token = ":".join(parts)
    return {"id_token": token, "email": email, "sub": sub}
