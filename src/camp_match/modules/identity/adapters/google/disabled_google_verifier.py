"""Disabled Google verifier raising GoogleSignInDisabled."""

from __future__ import annotations

from camp_match.modules.identity.application.errors import GoogleSignInDisabled
from camp_match.modules.identity.application.ports.outbound import VerifiedGoogleIdentity


class DisabledGoogleVerifier:
    async def verify(self, id_token_str: str, nonce: str | None = None) -> VerifiedGoogleIdentity:
        raise GoogleSignInDisabled("Google sign-in is not available.")
