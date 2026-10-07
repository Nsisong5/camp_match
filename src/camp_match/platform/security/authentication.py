from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from camp_match.modules.identity.adapters.api.dependencies import get_auth_session
from camp_match.modules.identity.adapters.security.jwt_session import (
    JwtAuthenticationSessionAdapter,
)
from camp_match.shared_kernel.domain.identifiers import EntityId

security_scheme = HTTPBearer(auto_error=False)


async def get_current_identity_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
    auth: Annotated[JwtAuthenticationSessionAdapter, Depends(get_auth_session)] = ...,  # type: ignore
) -> EntityId:
    if not credentials or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    return await auth.decode_access_token(credentials.credentials)
