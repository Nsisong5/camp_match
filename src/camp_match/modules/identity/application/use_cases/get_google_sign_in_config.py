"""Get Google sign-in configuration use case."""

from __future__ import annotations

from camp_match.config.settings import Settings
from camp_match.modules.identity.application.ports.inbound import (
    GoogleSignInConfigResponse,
)


class GetGoogleSignInConfigUseCase:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def execute(self) -> GoogleSignInConfigResponse:
        backend = self._settings.google_auth_backend.lower()
        env = self._settings.app_env.lower()
        is_local_or_test = env in ("local", "test")

        real_enabled = backend in ("google", "both")
        mock_enabled = is_local_or_test and backend in ("fake", "both")
        enabled = real_enabled or mock_enabled
        client_ids = self._settings.google_oauth_client_ids_list if real_enabled else []

        return GoogleSignInConfigResponse(
            enabled=enabled,
            real_enabled=real_enabled,
            mock_enabled=mock_enabled,
            client_ids=client_ids,
        )
