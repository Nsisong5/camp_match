from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from camp_match.config.settings import get_settings
from camp_match.modules.identity.adapters.api.dependencies import get_auth_session
from camp_match.modules.identity.adapters.security.jwt_session import (
    JwtAuthenticationSessionAdapter,
)
from camp_match.modules.identity.application.errors import InvalidCredentials
from camp_match.shared_kernel.domain.identifiers import EntityId

security_scheme = HTTPBearer(auto_error=False)


async def decode_access_token_string(token: str, secret_key: str | None = None) -> EntityId:
    """Decode a raw access token string without an HTTP request."""
    key = secret_key or get_settings().jwt_secret_key
    try:
        payload = jwt.decode(token, key, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise InvalidCredentials("Invalid credentials.")
        return EntityId.from_string(payload["sub"])
    except jwt.PyJWTError as e:
        raise InvalidCredentials("Invalid credentials.") from e


async def get_current_identity_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
    auth: Annotated[JwtAuthenticationSessionAdapter, Depends(get_auth_session)] = ...,  # type: ignore
) -> EntityId:
    if not credentials or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    try:
        return await decode_access_token_string(credentials.credentials)
    except InvalidCredentials:
        raise HTTPException(status_code=401, detail="Missing or invalid token")
