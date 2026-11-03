from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from camp_match.modules.payment.adapters.api import dependencies
from camp_match.modules.payment.application.use_cases.process_webhook_event import (
    ProcessWebhookEventUseCase,
)

router = APIRouter(prefix="/api/v1/payments/webhooks", tags=["Payment Webhooks"])


@router.post("/{provider_name}", status_code=status.HTTP_200_OK)
async def process_webhook(
    provider_name: str,
    request: Request,
    use_case: Annotated[ProcessWebhookEventUseCase, Depends(dependencies.get_process_webhook_use_case)],
) -> dict[str, str]:
    body = await request.body()
    headers = dict(request.headers)
    await use_case.execute(provider_name, body, headers)
    return {"status": "received"}
