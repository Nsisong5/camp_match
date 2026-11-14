from __future__ import annotations

import json
import uuid
from typing import Annotated, Any
from uuid import UUID
from enum import StrEnum

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from camp_match.modules.payment.adapters.api.dependencies import (
    get_booking_provider,
    get_payment_attempt_repo,
    get_process_webhook_use_case,
    get_webhook_event_repo,
)
from camp_match.modules.payment.application.ports.outbound import (
    BookingProvider,
    PaymentAttemptRepository,
    WebhookEventRepository,
)
from camp_match.modules.payment.application.use_cases.process_webhook_event import (
    ProcessWebhookEventUseCase,
)
from camp_match.modules.payment.domain.value_objects import (
    PaymentAttemptStatus,
    WebhookProcessingOutcome,
)
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/payment-mock-controls", tags=["Payment Mock Controls"])

_mock_adapter_instance: Any | None = None


def set_global_mock_adapter(adapter: Any) -> None:
    global _mock_adapter_instance
    _mock_adapter_instance = adapter


class MockScenario(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING_THEN_SUCCESS = "pending_then_success"
    PENDING_THEN_FAILURE = "pending_then_failure"
    TIMEOUT = "timeout"
    DUPLICATE_WEBHOOK = "duplicate_webhook"
    INVALID_SIGNATURE = "invalid_signature"
    AMOUNT_MISMATCH = "amount_mismatch"
    UNCERTAIN_OUTCOME = "uncertain_outcome"


class SetScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: MockScenario = Field(
        ...,
        description="The mock payment scenario to execute.",
        examples=["success"],
    )


class SimulateWebhookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: MockScenario = Field(
        ...,
        description="The scenario simulation for webhook processing.",
        examples=["success"],
    )
    amount_kobo: int | None = Field(
        None,
        description="Optional amount override in kobo for testing amount mismatches.",
        examples=[10000],
    )
    invalid_signature: bool | None = Field(
        None,
        description="Whether to simulate an invalid signature.",
        examples=[False],
    )


class MockControlReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool
    action: str
    attempt: dict[str, Any]
    booking: dict[str, Any] | None
    payment_created: bool
    webhook_outcome: str | None
    reason_code: str | None
    message: str
    next_steps: list[str]


@router.get("/scenarios", response_model=list[dict[str, str]])
async def get_scenarios() -> list[dict[str, str]]:
    return [
        {
            "scenario": s.value,
            "description": f"Scenario {s.value} simulation for payment and booking integration.",
            "control": "simulate-webhook",
            "expected_result": "Results in corresponding payment and booking state update.",
        }
        for s in MockScenario
    ]


@router.get("/{attempt_id}", response_model=dict[str, Any])
async def inspect_attempt(
    attempt_id: UUID,
    attempt_repo: Annotated[PaymentAttemptRepository, Depends(get_payment_attempt_repo)],
    booking_provider: Annotated[BookingProvider, Depends(get_booking_provider)],
    webhook_repo: Annotated[WebhookEventRepository, Depends(get_webhook_event_repo)],
) -> dict[str, Any]:
    attempt = await attempt_repo.get_by_id(EntityId(attempt_id))
    if not attempt:
        raise HTTPException(status_code=404, detail="Payment attempt not found.")

    booking = await booking_provider.get_booking(attempt.booking_id)

    return {
        "attempt_id": str(attempt.id),
        "attempt_status": attempt.status.value,
        "scenario": _mock_adapter_instance._scenarios.get(str(attempt.id), "success") if _mock_adapter_instance else "success",
        "booking": {
            "id": str(booking.id) if booking else None,
            "status": booking.status if booking else None,
            "closure": None,
        } if booking else None,
        "payment_created": attempt.status == PaymentAttemptStatus.SUCCEEDED,
        "recent_webhooks": [],
        "next_steps": ["Proceed with webhook simulation or verification."],
    }


@router.post("/{attempt_id}/scenario", response_model=MockControlReport, status_code=status.HTTP_200_OK)
async def set_mock_scenario(
    attempt_id: UUID,
    body: SetScenarioRequest,
    attempt_repo: Annotated[PaymentAttemptRepository, Depends(get_payment_attempt_repo)],
    booking_provider: Annotated[BookingProvider, Depends(get_booking_provider)],
) -> MockControlReport:
    attempt = await attempt_repo.get_by_id(EntityId(attempt_id))
    if not attempt:
        raise HTTPException(status_code=404, detail="Payment attempt not found.")

    if attempt.status.value in {"SUCCEEDED", "FAILED", "EXPIRED", "CANCELLED"}:
        raise HTTPException(status_code=409, detail="Cannot change scenario for attempt in terminal state.")

    if _mock_adapter_instance:
        _mock_adapter_instance.set_scenario(str(attempt.id), body.scenario.value)

    booking = await booking_provider.get_booking(attempt.booking_id)

    return MockControlReport(
        ok=True,
        action="set_scenario",
        attempt={"id": str(attempt.id), "status_before": attempt.status.value, "status_after": attempt.status.value},
        booking={"id": str(booking.id) if booking else None, "status_before": booking.status if booking else None, "status_after": booking.status if booking else None} if booking else None,
        payment_created=attempt.status == PaymentAttemptStatus.SUCCEEDED,
        webhook_outcome=None,
        reason_code=None,
        message=f"Scenario successfully set to {body.scenario.value}.",
        next_steps=["Simulate webhook to process payment attempt."],
    )


@router.post("/{attempt_id}/simulate-webhook", response_model=MockControlReport, status_code=status.HTTP_200_OK)
async def simulate_webhook(
    attempt_id: UUID,
    body: SimulateWebhookRequest,
    attempt_repo: Annotated[PaymentAttemptRepository, Depends(get_payment_attempt_repo)],
    booking_provider: Annotated[BookingProvider, Depends(get_booking_provider)],
    process_webhook_uc: Annotated[ProcessWebhookEventUseCase, Depends(get_process_webhook_use_case)],
) -> MockControlReport:
    attempt = await attempt_repo.get_by_id(EntityId(attempt_id))
    if not attempt:
        raise HTTPException(status_code=404, detail="Payment attempt not found.")

    status_before = attempt.status.value
    booking_before = await booking_provider.get_booking(attempt.booking_id)
    booking_status_before = booking_before.status if booking_before else None

    event_type = "payment.success"
    status_str = "SUCCEEDED"
    if body.scenario == MockScenario.FAILURE:
        event_type = "payment.failure"
        status_str = "FAILED"
    elif body.scenario == MockScenario.TIMEOUT:
        event_type = "payment.timeout"
        status_str = "EXPIRED"

    raw_payload = {
        "event_id": f"evt_{uuid.uuid4()}",
        "event_type": event_type,
        "provider_reference": attempt.provider_reference or f"mock_prov_ref_{attempt.id.value}",
        "status": status_str,
        "amount_kobo": body.amount_kobo if body.amount_kobo is not None else attempt.amount.amount_kobo,
    }
    if body.invalid_signature or body.scenario == MockScenario.INVALID_SIGNATURE:
        raw_payload["invalid_signature"] = True

    raw_body = json.dumps(raw_payload).encode("utf-8")
    headers = {"x-mock-signature": "invalid" if (body.invalid_signature or body.scenario == MockScenario.INVALID_SIGNATURE) else "valid"}

    outcome, reason_code = await process_webhook_uc.execute("mock", raw_body, headers)

    attempt_after = await attempt_repo.get_by_id(EntityId(attempt_id))
    booking_after = await booking_provider.get_booking(attempt.booking_id)
    status_after = attempt_after.status.value if attempt_after else status_before
    booking_status_after = booking_after.status if booking_after else booking_status_before

    ok = outcome in {WebhookProcessingOutcome.PROCESSED_CONFIRMED, WebhookProcessingOutcome.LATE_SUCCESS_FLAGGED}
    message = f"Webhook processed with outcome {outcome.value}."
    if reason_code == "late_success":
        ok = True
        message = "The webhook was received but flagged for late payment review because the hold had expired."
    elif outcome == WebhookProcessingOutcome.REJECTED_INVALID_SIGNATURE:
        ok = False
        message = "Webhook rejected due to invalid signature."
    elif outcome == WebhookProcessingOutcome.REJECTED_AMOUNT_MISMATCH:
        ok = False
        message = "Webhook rejected due to amount mismatch."
    elif outcome == WebhookProcessingOutcome.IGNORED_DUPLICATE:
        ok = True
        message = "Duplicate webhook ignored."
    elif outcome == WebhookProcessingOutcome.UNCORRELATED:
        ok = False
        message = "Webhook uncorrelated."

    return MockControlReport(
        ok=ok,
        action="simulate_webhook",
        attempt={"id": str(attempt.id), "status_before": status_before, "status_after": status_after},
        booking={"id": str(booking_before.id) if booking_before else None, "status_before": booking_status_before, "status_after": booking_status_after} if booking_before else None,
        payment_created=status_after == "SUCCEEDED",
        webhook_outcome=outcome.value,
        reason_code=reason_code,
        message=message,
        next_steps=["Inspect attempt for details."],
    )
