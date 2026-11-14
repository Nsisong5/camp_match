"""Real Google ID token verifier using google-auth and requests."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from camp_match.config.settings import Settings
from camp_match.modules.identity.application.errors import InvalidGoogleToken
from camp_match.modules.identity.application.ports.outbound import VerifiedGoogleIdentity

logger = structlog.get_logger()


class GoogleIdTokenVerifier:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client_ids = settings.google_oauth_client_ids_list
        self._require_nonce = settings.google_require_nonce
        self._timeout = settings.google_verify_timeout_seconds

    async def verify(
        self, id_token_str: str, nonce: str | None = None
    ) -> VerifiedGoogleIdentity:
        logger.info("google_verification_started")

        # Enforce required format of the token information
        if not id_token_str or not isinstance(id_token_str, str) or not id_token_str.strip():
            logger.warning(
                "google_verification_failed",
                stage="token_format_validation",
                error_type="InvalidTokenFormat",
            )
            raise InvalidGoogleToken("Google ID token is not in the required format.")

        # Basic JWT structure check (header.payload.signature typically contains dots)
        parts = id_token_str.strip().split(".")
        if len(parts) < 3 and not id_token_str.startswith("fake:"):
            logger.warning(
                "google_verification_failed",
                stage="token_format_validation",
                error_type="InvalidJWTStructure",
            )
            raise InvalidGoogleToken("Google ID token is not in the required format.")

        if self._require_nonce and not nonce:
            logger.warning(
                "google_verification_failed",
                stage="nonce_validation",
                error_type="MissingNonce",
            )
            raise InvalidGoogleToken("Nonce is required but was not supplied.")

        logger.info("google_token_input_validated")

        try:
            loop = asyncio.get_running_loop()

            def _verify() -> dict[str, Any]:
                request = google_requests.Request()
                # Per ADR-215 / spec: call verify_oauth2_token without audience.
                payload = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
                    id_token_str, request, audience=None
                )
                return payload  # type: ignore[no-any-return]

            logger.info("google_verification_library_started")
            payload = await asyncio.wait_for(
                loop.run_in_executor(None, _verify),
                timeout=self._timeout,
            )
            logger.info("google_verification_library_completed")

            # Check audience against configured client IDs if any
            aud = payload.get("aud")
            if self._client_ids and aud not in self._client_ids:
                logger.warning(
                    "google_verification_failed",
                    stage="audience_validation",
                    error_type="InvalidAudience",
                )
                raise InvalidGoogleToken("Invalid audience in Google token.")
            logger.info("google_audience_validation_completed")

            # Check issuer
            iss = payload.get("iss")
            if iss not in ("accounts.google.com", "https://accounts.google.com"):
                logger.warning(
                    "google_verification_failed",
                    stage="issuer_validation",
                    error_type="InvalidIssuer",
                )
                raise InvalidGoogleToken("Invalid issuer in Google token.")
            logger.info("google_issuer_validation_completed")

            # Check nonce if configured or supplied
            token_nonce = payload.get("nonce")
            if (nonce or self._require_nonce) and (
                not nonce or token_nonce != nonce
            ):
                logger.warning(
                    "google_verification_failed",
                    stage="nonce_validation",
                    error_type="InvalidNonce",
                )
                raise InvalidGoogleToken(
                    "Invalid or missing nonce in Google token."
                )
            logger.info("google_nonce_validation_completed")

            sub = payload.get("sub")
            email = payload.get("email")
            email_verified = payload.get("email_verified", False)
            hosted_domain = payload.get("hd")

            if (
                not sub
                or not isinstance(sub, str)
                or not email
                or not isinstance(email, str)
            ):
                logger.warning(
                    "google_verification_failed",
                    stage="claims_normalization",
                    error_type="MissingClaims",
                )
                raise InvalidGoogleToken("Google token missing sub or email claims.")

            logger.info("google_claims_normalized")
            logger.info("google_verification_completed", identity_sub_present=True)

            return VerifiedGoogleIdentity(
                subject=sub,
                email=email,
                email_verified=bool(email_verified),
                hosted_domain=hosted_domain,
            )
        except TimeoutError as e:
            logger.error(
                "google_verification_failed",
                stage="timeout",
                error_type="TimeoutError",
            )
            raise InvalidGoogleToken("Google verification timed out.") from e
        except InvalidGoogleToken:
            raise
        except ValueError as e:
            logger.error(
                "google_verification_failed",
                stage="verification_library",
                error_type="InvalidValue",
            )
            raise InvalidGoogleToken("Google ID token is not in the required format.") from e
        except Exception as e:
            logger.error(
                "google_verification_failed",
                stage="verification_library",
                error_type=e.__class__.__name__,
            )
            raise InvalidGoogleToken("Google sign-in could not be verified.") from e
