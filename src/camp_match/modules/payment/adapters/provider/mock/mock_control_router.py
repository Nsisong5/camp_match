from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, status

router = APIRouter(prefix="/api/v1/payment-mock-controls", tags=["Payment Mock Controls"])

_mock_adapter_instance: Any | None = None


def set_global_mock_adapter(adapter: Any) -> None:
    global _mock_adapter_instance
    _mock_adapter_instance = adapter


@router.post("/{attempt_id}/scenario", status_code=status.HTTP_204_NO_CONTENT)
async def set_mock_scenario(
    attempt_id: UUID,
    scenario: Annotated[str, Body(embed=True)],
) -> None:
    if _mock_adapter_instance:
        _mock_adapter_instance.set_scenario(str(attempt_id), scenario)


@router.post("/{attempt_id}/simulate-webhook", status_code=status.HTTP_200_OK)
async def simulate_webhook(
    attempt_id: UUID,
    payload: Annotated[dict[str, Any], Body()],
) -> dict[str, str]:
    return {"status": "simulated", "attempt_id": str(attempt_id)}
