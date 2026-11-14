from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, status

from camp_match.modules.identity.adapters.api import schemas
from camp_match.modules.identity.adapters.api.dependencies import (
    get_authenticate_user,
    get_get_identity,
    get_google_sign_in_config,
    get_link_google,
    get_logout,
    get_refresh_session,
    get_register_account,
    get_resend_verification,
    get_set_password,
    get_sign_in_with_google,
    get_unlink_google,
    get_verify_email,
)
from camp_match.modules.identity.application.ports.inbound import (
    AuthenticationRequest,
    GoogleSignInRequest,
    IdentityQueryRequest,
    LinkGoogleRequest,
    LogoutRequest,
    RefreshRequest,
    RegistrationRequest,
    ResendVerificationRequest,
    SetPasswordRequest,
    UnlinkGoogleRequest,
    VerifyEmailRequest,
)
from camp_match.modules.identity.application.use_cases.authenticate_user import (
    AuthenticateUserUseCase,
)
from camp_match.modules.identity.application.use_cases.get_google_sign_in_config import (
    GetGoogleSignInConfigUseCase,
)
from camp_match.modules.identity.application.use_cases.get_identity import (
    GetIdentityByIdUseCase,
)
from camp_match.modules.identity.application.use_cases.link_google_account import (
    LinkGoogleAccountUseCase,
)
from camp_match.modules.identity.application.use_cases.logout import LogoutUseCase
from camp_match.modules.identity.application.use_cases.refresh_session import (
    RefreshSessionUseCase,
)
from camp_match.modules.identity.application.use_cases.register_account import (
    RegisterAccountUseCase,
)
from camp_match.modules.identity.application.use_cases.resend_email_verification import (
    ResendEmailVerificationUseCase,
)
from camp_match.modules.identity.application.use_cases.set_password import (
    SetPasswordUseCase,
)
from camp_match.modules.identity.application.use_cases.sign_in_with_google import (
    SignInWithGoogleUseCase,
)
from camp_match.modules.identity.application.use_cases.unlink_google_account import (
    UnlinkGoogleAccountUseCase,
)
from camp_match.modules.identity.application.use_cases.verify_email import (
    VerifyEmailUseCase,
)
from camp_match.platform.security.authentication import get_current_identity_id
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.RegisterResponse,
)
async def register(
    reg_request: schemas.RegisterRequest,
    use_case: Annotated[RegisterAccountUseCase, Depends(get_register_account)],
) -> schemas.RegisterResponse:
    registration_request = RegistrationRequest(
        email=reg_request.email, raw_password=reg_request.password
    )
    identity = await use_case.execute(registration_request)
    return schemas.RegisterResponse(
        id=identity.id,
        email=identity.email,
        email_verification_required=identity.email_verification_required,
    )


@router.post(
    "/login", status_code=status.HTTP_200_OK, response_model=schemas.LoginResponse
)
async def login(
    login_request: schemas.LoginRequest,
    use_case: Annotated[AuthenticateUserUseCase, Depends(get_authenticate_user)],
) -> schemas.LoginResponse:
    auth_request = AuthenticationRequest(
        email=login_request.email, raw_password=login_request.password
    )
    tokens = await use_case.execute(auth_request)
    return schemas.LoginResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.get("/me", status_code=status.HTTP_200_OK, response_model=schemas.MeResponse)
async def me(
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[GetIdentityByIdUseCase, Depends(get_get_identity)],
) -> schemas.MeResponse:
    query_request = IdentityQueryRequest(identity_id=str(identity_id))
    identity = await use_case.execute(query_request)
    return schemas.MeResponse(
        id=identity.id,
        email=identity.email,
        status=identity.status,
        email_verified=identity.email_verified,
        sign_in_methods=identity.sign_in_methods,
    )


@router.post(
    "/refresh", status_code=status.HTTP_200_OK, response_model=schemas.RefreshResponse
)
async def refresh(
    refresh_data: Annotated[schemas.RefreshRequest, Body(...)],
    use_case: Annotated[RefreshSessionUseCase, Depends(get_refresh_session)],
) -> schemas.RefreshResponse:
    refresh_request = RefreshRequest(refresh_token=refresh_data.refresh_token)
    tokens = await use_case.execute(refresh_request)
    return schemas.RefreshResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    logout_data: Annotated[schemas.RefreshRequest, Body(...)],
    use_case: Annotated[LogoutUseCase, Depends(get_logout)],
) -> None:
    logout_request = LogoutRequest(refresh_token=logout_data.refresh_token)
    await use_case.execute(logout_request)


@router.post(
    "/verify-email",
    status_code=status.HTTP_200_OK,
    response_model=schemas.VerifyEmailResponseSchema,
)
async def verify_email(
    body: schemas.VerifyEmailRequestSchema,
    use_case: Annotated[VerifyEmailUseCase, Depends(get_verify_email)],
) -> schemas.VerifyEmailResponseSchema:
    res = await use_case.execute(
        VerifyEmailRequest(email=body.email, code=body.code)
    )
    return schemas.VerifyEmailResponseSchema(verified=res.verified)


@router.post(
    "/resend-verification",
    status_code=status.HTTP_202_ACCEPTED,
)
async def resend_verification(
    body: schemas.ResendVerificationRequestSchema,
    use_case: Annotated[
        ResendEmailVerificationUseCase, Depends(get_resend_verification)
    ],
) -> None:
    await use_case.execute(ResendVerificationRequest(email=body.email))


@router.post(
    "/google",
    status_code=status.HTTP_200_OK,
    response_model=schemas.GoogleSignInResponseSchema,
)
async def google_sign_in(
    body: schemas.GoogleSignInRequestSchema,
    use_case: Annotated[SignInWithGoogleUseCase, Depends(get_sign_in_with_google)],
) -> schemas.GoogleSignInResponseSchema:
    res = await use_case.execute(
        GoogleSignInRequest(id_token=body.id_token, nonce=body.nonce)
    )
    return schemas.GoogleSignInResponseSchema(
        access_token=res.access_token,
        refresh_token=res.refresh_token,
        token_type=res.token_type,
        expires_in=res.expires_in,
        is_new_account=res.is_new_account,
    )


@router.post(
    "/google/link",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def link_google(
    body: schemas.LinkGoogleRequestSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[LinkGoogleAccountUseCase, Depends(get_link_google)],
) -> None:
    await use_case.execute(
        LinkGoogleRequest(
            identity_id=str(identity_id),
            id_token=body.id_token,
            nonce=body.nonce,
        )
    )


@router.post(
    "/google/unlink",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_google(
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[UnlinkGoogleAccountUseCase, Depends(get_unlink_google)],
) -> None:
    await use_case.execute(UnlinkGoogleRequest(identity_id=str(identity_id)))


@router.post(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def set_password(
    body: schemas.SetPasswordRequestSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[SetPasswordUseCase, Depends(get_set_password)],
) -> None:
    await use_case.execute(
        SetPasswordRequest(identity_id=str(identity_id), raw_password=body.password)
    )


@router.get(
    "/google/config",
    status_code=status.HTTP_200_OK,
    response_model=schemas.GoogleConfigResponse,
)
async def get_google_config(
    use_case: Annotated[
        GetGoogleSignInConfigUseCase, Depends(get_google_sign_in_config)
    ],
) -> schemas.GoogleConfigResponse:
    config = await use_case.execute()
    return schemas.GoogleConfigResponse(
        enabled=config.enabled,
        real_enabled=config.real_enabled,
        mock_enabled=config.mock_enabled,
        client_ids=config.client_ids,
    )
