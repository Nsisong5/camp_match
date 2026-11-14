"""Composite Google verifier selecting verifier based on google_auth_backend."""

from __future__ import annotations

from camp_match.config.settings import Settings
from camp_match.modules.identity.adapters.google.disabled_google_verifier import (
    DisabledGoogleVerifier,
)
from camp_match.modules.identity.adapters.google.fake_google_verifier import (
    FakeGoogleVerifier,
)
from camp_match.modules.identity.adapters.google.google_id_token_verifier import (
    GoogleIdTokenVerifier,
)
from camp_match.modules.identity.application.errors import GoogleSignInDisabled
from camp_match.modules.identity.application.ports.outbound import VerifiedGoogleIdentity


class CompositeGoogleVerifier:
    def __init__(self, settings: Settings) -> None:
        self._backend = settings.google_auth_backend.lower()
        self._real_verifier = GoogleIdTokenVerifier(settings)
        self._fake_verifier = FakeGoogleVerifier()
        self._disabled_verifier = DisabledGoogleVerifier()

    async def verify(self, id_token_str: str, nonce: str | None = None) -> VerifiedGoogleIdentity:
        if self._backend == "disabled":
            return await self._disabled_verifier.verify(id_token_str, nonce)

        if self._backend == "google":
            return await self._real_verifier.verify(id_token_str, nonce)

        if self._backend == "fake":
            return await self._fake_verifier.verify(id_token_str, nonce)

        if self._backend == "both":
            if id_token_str.startswith("fake:"):
                return await self._fake_verifier.verify(id_token_str, nonce)
            else:
                return await self._real_verifier.verify(id_token_str, nonce)

        raise GoogleSignInDisabled("Google sign-in is not available.")
