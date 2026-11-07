from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from camp_match.modules.payment.adapters.api import dependencies, schemas
from camp_match.modules.payment.application.errors import PaymentError
from camp_match.modules.payment.application.ports.inbound import InitiatePaymentRequest
from camp_match.modules.payment.application.use_cases.execute_refund import ExecuteRefundUseCase
from camp_match.modules.payment.application.use_cases.execute_release import ExecuteReleaseUseCase
from camp_match.modules.payment.application.use_cases.initiate_payment import InitiatePaymentUseCase
from camp_match.modules.payment.domain.value_objects import Money
from camp_match.modules.security.adapters.api.dependencies import (
    get_current_identity_id,
    require_permission,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@router.post("", response_model=schemas.PaymentSessionResponseSchema, status_code=status.HTTP_201_CREATED)
async def initiate_payment(
    body: schemas.CreatePaymentSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[InitiatePaymentUseCase, Depends(dependencies.get_initiate_payment_use_case)],
) -> schemas.PaymentSessionResponseSchema:
    try:
        result = await use_case.execute(
            InitiatePaymentRequest(
                booking_id=EntityId(body.booking_id),
                caller_id=identity_id,
                idempotency_key=body.idempotency_key,
                provider_name=body.provider_name,
            )
        )
        return schemas.PaymentSessionResponseSchema(
            provider_reference=result.provider_reference,
            checkout_reference=result.checkout_reference,
            expires_at=result.expires_at,
        )
    except PaymentError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/disputes/pending", response_model=list[schemas.DisputeResponseSchema])
async def list_pending_disputes(
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    dispute_repo: Annotated[Any, Depends(dependencies.get_dispute_repo)],
    _ = require_permission(Permission.PAYMENT_REVIEW),
) -> list[schemas.DisputeResponseSchema]:
    return []


@router.post("/{payment_id}/release", status_code=status.HTTP_204_NO_CONTENT)
async def release_payment(
    payment_id: UUID,
    body: schemas.ReleaseRequestSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    payment_repo: Annotated[Any, Depends(dependencies.get_payment_repo)],
    fd_repo: Annotated[Any, Depends(dependencies.get_fund_disposition_repo)],
    decision_repo: Annotated[Any, Depends(dependencies.get_release_decision_repo)],
    execute_release: Annotated[ExecuteReleaseUseCase, Depends(dependencies.get_execute_release_use_case)],
    _ = require_permission(Permission.PAYMENT_AUTHORIZE_RELEASE),
) -> None:
    payment = await payment_repo.get_by_id(EntityId(payment_id))
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    fd = await fd_repo.get_by_payment_id(payment.id)
    if not fd:
        raise HTTPException(status_code=404, detail="Fund disposition not found")

    decision_id = EntityId.new()
    await decision_repo.add(
        decision_id=decision_id,
        fund_disposition_id=fd.id,
        decision="RELEASE",
        amount_kobo=fd.remaining_releasable_kobo,
        currency="NGN",
        policy_version="1.0",
        triggering_fact="manual_admin_decision",
        origin="MANUAL",
        reason=body.reason,
        decided_at=dependencies.get_clock().now(),
        authorized_by=identity_id,
    )
    await execute_release.execute(
        decision_id=decision_id,
        fund_disposition_id=fd.id,
        amount=Money(fd.remaining_releasable_kobo),
        recipient_reference="manual_release_ref",
    )


@router.post("/{payment_id}/refund", status_code=status.HTTP_204_NO_CONTENT)
async def refund_payment(
    payment_id: UUID,
    body: schemas.RefundRequestSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    payment_repo: Annotated[Any, Depends(dependencies.get_payment_repo)],
    fd_repo: Annotated[Any, Depends(dependencies.get_fund_disposition_repo)],
    execute_refund: Annotated[ExecuteRefundUseCase, Depends(dependencies.get_execute_refund_use_case)],
    _ = require_permission(Permission.PAYMENT_AUTHORIZE_REFUND),
) -> None:
    payment = await payment_repo.get_by_id(EntityId(payment_id))
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    fd = await fd_repo.get_by_payment_id(payment.id)
    if not fd:
        raise HTTPException(status_code=404, detail="Fund disposition not found")

    decision_id = EntityId.new()
    await execute_refund.execute(
        decision_id=decision_id,
        fund_disposition_id=fd.id,
        amount=payment.amount,
        provider_reference=payment.provider_reference,
    )
