from __future__ import annotations

from typing import Any

import httpx
import structlog
from camp_match.config.settings import Settings
from camp_match.modules.payment.adapters.provider.paystack.errors import (
    PaystackConnectionError,
    PaystackParsingError,
    PaystackRejectedError,
    PaystackUncertainError,
)
from pydantic import ValidationError

logger = structlog.get_logger(__name__)

class PaystackClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        secret = settings.paystack_secret_key
        secret_value = secret.get_secret_value() if secret else ""
        self._client = httpx.AsyncClient(
            base_url=settings.paystack_base_url,
            headers={
                "Authorization": f"Bearer {secret_value}",
                "User-Agent": "CampMatchAPI/1.0",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(
                connect=settings.paystack_connect_timeout_seconds,
                read=settings.paystack_read_timeout_seconds,
                write=30.0,
                pool=5.0
            ),
            follow_redirects=False,
            verify=True,
        )

    async def post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(path, json=json)
            return self._handle_response(response)
        except httpx.ConnectError as e:
            raise PaystackConnectionError(f"Connection failed: {e}") from e
        except httpx.TimeoutException as e:
            raise PaystackUncertainError(f"Timeout: {e}") from e

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = await self._client.get(path, params=params)
            return self._handle_response(response)
        except httpx.ConnectError as e:
            raise PaystackConnectionError(f"Connection failed: {e}") from e
        except httpx.TimeoutException as e:
            raise PaystackUncertainError(f"Timeout: {e}") from e

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        if 200 <= response.status_code < 300:
            try:
                data = response.json()
                if not data.get("status"):
                     raise PaystackRejectedError(f"Provider rejected: {data.get('message')}")
                return data # type: ignore[no-any-return]
            except (ValueError, ValidationError) as e:
                raise PaystackParsingError(f"Parsing failed: {e}") from e
        
        if response.status_code in (400, 401, 403, 404, 422):
            raise PaystackRejectedError(f"Rejected with status {response.status_code}")
        
        raise PaystackUncertainError(f"Uncertain status {response.status_code}")
