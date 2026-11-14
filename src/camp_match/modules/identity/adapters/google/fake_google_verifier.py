"""Fake Google ID token verifier for local/test environments."""

from __future__ import annotations

from camp_match.modules.identity.application.errors import InvalidGoogleToken
from camp_match.modules.identity.application.ports.outbound import VerifiedGoogleIdentity


class FakeGoogleVerifier:
    async def verify(self, id_token_str: str, nonce: str | None = None) -> VerifiedGoogleIdentity:
        if not id_token_str or not id_token_str.startswith("fake:"):
            raise InvalidGoogleToken("Invalid fake Google token format.")

        parts = id_token_str.split(":")
        if len(parts) < 3:
            raise InvalidGoogleToken("Malformed fake Google token.")

        email = parts[1]
        subject = parts[2]
        unverified = "unverified" in parts
        hosted_domain = None

        for part in parts[3:]:
            if part.startswith("hd="):
                hosted_domain = part.split("=")[1]

        email_verified = not unverified

        return VerifiedGoogleIdentity(
            subject=subject,
            email=email,
            email_verified=email_verified,
            hosted_domain=hosted_domain,
        )
