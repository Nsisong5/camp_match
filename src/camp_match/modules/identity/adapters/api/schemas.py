"""Identity API schemas with extra='forbid' and descriptive fields."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")


class RegisterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., description="Identity account ID")
    email: EmailStr = Field(..., description="User email address")
    email_verification_required: bool = Field(
        ..., description="Whether email verification is required"
    )


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(..., description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., description="Identity account ID")
    email: EmailStr = Field(..., description="User email address")
    status: str = Field(..., description="Account status")
    email_verified: bool = Field(..., description="Whether email is verified")
    sign_in_methods: list[str] = Field(..., description="Available sign-in methods")


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(..., description="JWT refresh token")


class RefreshResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(..., description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


class GoogleConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = Field(..., description="Whether Google sign-in is enabled")
    real_enabled: bool = Field(..., description="Whether real Google auth is enabled")
    mock_enabled: bool = Field(..., description="Whether mock Google auth is enabled")
    client_ids: list[str] = Field(..., description="OAuth client IDs")


class VerifyEmailRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(..., description="User email address")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class VerifyEmailResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verified: bool = Field(..., description="Verification result")


class ResendVerificationRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(..., description="User email address")


class GoogleSignInRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: str = Field(..., description="Google ID token")
    nonce: str | None = Field(None, description="Optional OAuth nonce")


class GoogleSignInResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(..., description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")
    is_new_account: bool = Field(..., description="Whether this is a newly registered account")


class LinkGoogleRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: str = Field(..., description="Google ID token")
    nonce: str | None = Field(None, description="Optional OAuth nonce")


class SetPasswordRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(..., min_length=8, max_length=128, description="New user password")
