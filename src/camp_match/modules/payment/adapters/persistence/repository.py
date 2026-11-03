from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from camp_match.modules.payment.adapters.persistence.models import (
    DisputeModel,
    FundDispositionModel,
    LedgerEntryModel,
    PaymentAttemptModel,
    PaymentModel,
    ProviderWebhookEventModel,
    RefundOperationModel,
    ReleaseDecisionModel,
    ReleaseOperationModel,
)
from camp_match.modules.payment.application.ports.outbound import WebhookEventRecord
from camp_match.modules.payment.domain.entities import (
    Dispute,
    FundDisposition,
    Payment,
    PaymentAttempt,
    RefundOperation,
    ReleaseOperation,
)
from camp_match.modules.payment.domain.value_objects import (
    Currency,
    DisputeStatus,
    FundDispositionStatus,
    LedgerEntryType,
    Money,
    OperationStatus,
    PaymentAttemptStatus,
)
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyPaymentAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, attempt: PaymentAttempt) -> PaymentAttempt:
        model = PaymentAttemptModel(
            id=attempt.id.value,
            booking_id=attempt.booking_id.value,
            student_id=attempt.student_id.value,
            amount_kobo=attempt.amount.amount_kobo,
            currency=attempt.amount.currency.value,
            idempotency_key=attempt.idempotency_key,
            status=attempt.status.value,
            provider_name=attempt.provider_name,
            provider_reference=attempt.provider_reference,
            created_at=attempt.created_at,
            confirmed_at=attempt.confirmed_at,
        )
        try:
            self._session.add(model)
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            existing = await self.get_by_idempotency_key(attempt.student_id, attempt.idempotency_key)
            if existing:
                return existing
            raise
        return attempt

    async def get_by_id(self, attempt_id: EntityId) -> PaymentAttempt | None:
        stmt = select(PaymentAttemptModel).where(PaymentAttemptModel.id == attempt_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_idempotency_key(
        self, student_id: EntityId, idempotency_key: str
    ) -> PaymentAttempt | None:
        stmt = select(PaymentAttemptModel).where(
            PaymentAttemptModel.student_id == student_id.value,
            PaymentAttemptModel.idempotency_key == idempotency_key,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_provider_reference(self, provider_reference: str) -> PaymentAttempt | None:
        stmt = select(PaymentAttemptModel).where(
            PaymentAttemptModel.provider_reference == provider_reference
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def update_status(
        self,
        attempt_id: EntityId,
        status: PaymentAttemptStatus,
        provider_reference: str | None = None,
        confirmed_at: datetime | None = None,
    ) -> bool:
        values: dict[str, Any] = {"status": status.value}
        if provider_reference is not None:
            values["provider_reference"] = provider_reference
        if confirmed_at is not None:
            values["confirmed_at"] = confirmed_at

        stmt = (
            update(PaymentAttemptModel)
            .where(PaymentAttemptModel.id == attempt_id.value)
            .values(**values)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    def _to_domain(self, model: PaymentAttemptModel) -> PaymentAttempt:
        return PaymentAttempt(
            id=EntityId(model.id),
            booking_id=EntityId(model.booking_id),
            student_id=EntityId(model.student_id),
            amount=Money(amount_kobo=model.amount_kobo, currency=Currency(model.currency)),
            idempotency_key=model.idempotency_key,
            status=PaymentAttemptStatus(model.status),
            provider_name=model.provider_name,
            provider_reference=model.provider_reference,
            created_at=model.created_at,
            confirmed_at=model.confirmed_at,
        )


class SqlAlchemyPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, payment: Payment) -> Payment:
        model = PaymentModel(
            id=payment.id.value,
            payment_attempt_id=payment.payment_attempt_id.value,
            booking_id=payment.booking_id.value,
            student_id=payment.student_id.value,
            amount_kobo=payment.amount.amount_kobo,
            currency=payment.amount.currency.value,
            provider_reference=payment.provider_reference,
            confirmed_at=payment.confirmed_at,
        )
        self._session.add(model)
        await self._session.flush()
        return payment

    async def get_by_id(self, payment_id: EntityId) -> Payment | None:
        stmt = select(PaymentModel).where(PaymentModel.id == payment_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    def _to_domain(self, model: PaymentModel) -> Payment:
        return Payment(
            id=EntityId(model.id),
            payment_attempt_id=EntityId(model.payment_attempt_id),
            booking_id=EntityId(model.booking_id),
            student_id=EntityId(model.student_id),
            amount=Money(amount_kobo=model.amount_kobo, currency=Currency(model.currency)),
            provider_reference=model.provider_reference,
            confirmed_at=model.confirmed_at,
        )


class SqlAlchemyFundDispositionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, disposition: FundDisposition) -> FundDisposition:
        model = FundDispositionModel(
            id=disposition.id.value,
            payment_id=disposition.payment_id.value,
            held_amount_kobo=disposition.held_amount_kobo,
            status=disposition.status.value,
            created_at=disposition.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return disposition

    async def get_by_id(self, disposition_id: EntityId) -> FundDisposition | None:
        stmt = select(FundDispositionModel).where(FundDispositionModel.id == disposition_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None

        rel_stmt = select(ReleaseOperationModel).where(ReleaseOperationModel.fund_disposition_id == model.id)
        rel_res = await self._session.execute(rel_stmt)
        rel_ops = [
            ReleaseOperation(
                id=EntityId(op.id),
                fund_disposition_id=EntityId(op.fund_disposition_id),
                amount=Money(op.amount_kobo),
                status=OperationStatus(op.status),
                decision_id=EntityId(op.decision_id),
                provider_operation_reference=op.provider_operation_reference,
                requested_at=op.requested_at,
                confirmed_at=op.confirmed_at,
                failure_reason=op.failure_reason,
            )
            for op in rel_res.scalars().all()
        ]

        ref_stmt = select(RefundOperationModel).where(RefundOperationModel.fund_disposition_id == model.id)
        ref_res = await self._session.execute(ref_stmt)
        ref_ops = [
            RefundOperation(
                id=EntityId(op.id),
                fund_disposition_id=EntityId(op.fund_disposition_id),
                amount=Money(op.amount_kobo),
                status=OperationStatus(op.status),
                decision_id=EntityId(op.decision_id),
                provider_operation_reference=op.provider_operation_reference,
                requested_at=op.requested_at,
                confirmed_at=op.confirmed_at,
                failure_reason=op.failure_reason,
            )
            for op in ref_res.scalars().all()
        ]

        return FundDisposition(
            id=EntityId(model.id),
            payment_id=EntityId(model.payment_id),
            held_amount_kobo=model.held_amount_kobo,
            status=FundDispositionStatus(model.status),
            created_at=model.created_at,
            release_operations=rel_ops,
            refund_operations=ref_ops,
        )

    async def update_status(self, disposition_id: EntityId, status: FundDispositionStatus) -> bool:
        stmt = (
            update(FundDispositionModel)
            .where(FundDispositionModel.id == disposition_id.value)
            .values(status=status.value)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlAlchemyReleaseOperationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, op: ReleaseOperation) -> ReleaseOperation:
        model = ReleaseOperationModel(
            id=op.id.value,
            fund_disposition_id=op.fund_disposition_id.value,
            amount_kobo=op.amount.amount_kobo,
            status=op.status.value,
            decision_id=op.decision_id.value,
            provider_operation_reference=op.provider_operation_reference,
            requested_at=op.requested_at,
            confirmed_at=op.confirmed_at,
            failure_reason=op.failure_reason,
        )
        self._session.add(model)
        await self._session.flush()
        return op

    async def get_by_decision_id(self, decision_id: EntityId) -> ReleaseOperation | None:
        stmt = select(ReleaseOperationModel).where(ReleaseOperationModel.decision_id == decision_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def update_status(
        self,
        op_id: EntityId,
        status: OperationStatus,
        provider_operation_reference: str | None = None,
        confirmed_at: datetime | None = None,
        failure_reason: str | None = None,
    ) -> bool:
        values: dict[str, Any] = {"status": status.value}
        if provider_operation_reference is not None:
            values["provider_operation_reference"] = provider_operation_reference
        if confirmed_at is not None:
            values["confirmed_at"] = confirmed_at
        if failure_reason is not None:
            values["failure_reason"] = failure_reason

        stmt = (
            update(ReleaseOperationModel)
            .where(ReleaseOperationModel.id == op_id.value)
            .values(**values)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    def _to_domain(self, model: ReleaseOperationModel) -> ReleaseOperation:
        return ReleaseOperation(
            id=EntityId(model.id),
            fund_disposition_id=EntityId(model.fund_disposition_id),
            amount=Money(model.amount_kobo),
            status=OperationStatus(model.status),
            decision_id=EntityId(model.decision_id),
            provider_operation_reference=model.provider_operation_reference,
            requested_at=model.requested_at,
            confirmed_at=model.confirmed_at,
            failure_reason=model.failure_reason,
        )


class SqlAlchemyRefundOperationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, op: RefundOperation) -> RefundOperation:
        model = RefundOperationModel(
            id=op.id.value,
            fund_disposition_id=op.fund_disposition_id.value,
            amount_kobo=op.amount.amount_kobo,
            status=op.status.value,
            decision_id=op.decision_id.value,
            provider_operation_reference=op.provider_operation_reference,
            requested_at=op.requested_at,
            confirmed_at=op.confirmed_at,
            failure_reason=op.failure_reason,
        )
        self._session.add(model)
        await self._session.flush()
        return op

    async def get_by_decision_id(self, decision_id: EntityId) -> RefundOperation | None:
        stmt = select(RefundOperationModel).where(RefundOperationModel.decision_id == decision_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def update_status(
        self,
        op_id: EntityId,
        status: OperationStatus,
        provider_operation_reference: str | None = None,
        confirmed_at: datetime | None = None,
        failure_reason: str | None = None,
    ) -> bool:
        values: dict[str, Any] = {"status": status.value}
        if provider_operation_reference is not None:
            values["provider_operation_reference"] = provider_operation_reference
        if confirmed_at is not None:
            values["confirmed_at"] = confirmed_at
        if failure_reason is not None:
            values["failure_reason"] = failure_reason

        stmt = (
            update(RefundOperationModel)
            .where(RefundOperationModel.id == op_id.value)
            .values(**values)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    def _to_domain(self, model: RefundOperationModel) -> RefundOperation:
        return RefundOperation(
            id=EntityId(model.id),
            fund_disposition_id=EntityId(model.fund_disposition_id),
            amount=Money(model.amount_kobo),
            status=OperationStatus(model.status),
            decision_id=EntityId(model.decision_id),
            provider_operation_reference=model.provider_operation_reference,
            requested_at=model.requested_at,
            confirmed_at=model.confirmed_at,
            failure_reason=model.failure_reason,
        )


class SqlAlchemyDisputeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, dispute: Dispute) -> Dispute:
        model = DisputeModel(
            id=dispute.id.value,
            fund_disposition_id=dispute.fund_disposition_id.value,
            raised_by=dispute.raised_by.value,
            reason=dispute.reason,
            status=dispute.status.value,
            raised_at=dispute.raised_at,
            resolved_at=dispute.resolved_at,
            resolved_by=dispute.resolved_by.value if dispute.resolved_by else None,
            resolution_notes=dispute.resolution_notes,
        )
        self._session.add(model)
        await self._session.flush()
        return dispute

    async def get_by_id(self, dispute_id: EntityId) -> Dispute | None:
        stmt = select(DisputeModel).where(DisputeModel.id == dispute_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_open_by_fund_disposition_id(self, disposition_id: EntityId) -> Dispute | None:
        stmt = select(DisputeModel).where(
            DisputeModel.fund_disposition_id == disposition_id.value,
            DisputeModel.status == DisputeStatus.OPEN.value,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    def _to_domain(self, model: DisputeModel) -> Dispute:
        return Dispute(
            id=EntityId(model.id),
            fund_disposition_id=EntityId(model.fund_disposition_id),
            raised_by=EntityId(model.raised_by),
            reason=model.reason,
            status=DisputeStatus(model.status),
            raised_at=model.raised_at,
            resolved_at=model.resolved_at,
            resolved_by=EntityId(model.resolved_by) if model.resolved_by else None,
            resolution_notes=model.resolution_notes,
        )

    async def update_resolution(
        self,
        dispute_id: EntityId,
        status: DisputeStatus,
        resolved_at: datetime,
        resolved_by: EntityId,
        resolution_notes: str,
    ) -> bool:
        stmt = (
            update(DisputeModel)
            .where(DisputeModel.id == dispute_id.value)
            .values(
                status=status.value,
                resolved_at=resolved_at,
                resolved_by=resolved_by.value,
                resolution_notes=resolution_notes,
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class SqlAlchemyWebhookEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        provider_name: str,
        provider_event_id: str,
        raw_payload_digest: str,
        normalized_event_type: str,
        processing_status: str,
        correlated_attempt_id: EntityId | None = None,
    ) -> WebhookEventRecord:
        model = ProviderWebhookEventModel(
            id=EntityId.new().value,
            provider_name=provider_name,
            provider_event_id=provider_event_id,
            raw_payload_digest=raw_payload_digest,
            normalized_event_type=normalized_event_type,
            processing_status=processing_status,
            correlated_attempt_id=correlated_attempt_id.value if correlated_attempt_id else None,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_domain(model)

    async def get_by_provider_event_id(self, provider_event_id: str) -> WebhookEventRecord | None:
        stmt = select(ProviderWebhookEventModel).where(
            ProviderWebhookEventModel.provider_event_id == provider_event_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def update_status(
        self,
        event_id: EntityId,
        status: str,
        processed_at: datetime,
        correlated_attempt_id: EntityId | None = None,
    ) -> bool:
        values: dict[str, Any] = {
            "processing_status": status,
            "processed_at": processed_at,
        }
        if correlated_attempt_id is not None:
            values["correlated_attempt_id"] = correlated_attempt_id.value

        stmt = (
            update(ProviderWebhookEventModel)
            .where(ProviderWebhookEventModel.id == event_id.value)
            .values(**values)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    def _to_domain(self, model: ProviderWebhookEventModel) -> WebhookEventRecord:
        return WebhookEventRecord(
            id=EntityId(model.id),
            provider_name=model.provider_name,
            provider_event_id=model.provider_event_id,
            raw_payload_digest=model.raw_payload_digest,
            normalized_event_type=model.normalized_event_type,
            correlated_attempt_id=EntityId(model.correlated_attempt_id) if model.correlated_attempt_id else None,
            processing_status=model.processing_status,
            received_at=model.received_at,
            processed_at=model.processed_at,
        )


class SqlAlchemyReleaseDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        decision_id: EntityId,
        fund_disposition_id: EntityId,
        decision: str,
        amount_kobo: int,
        currency: str,
        policy_version: str,
        triggering_fact: str,
        origin: str,
        reason: str,
        decided_at: datetime,
        evidence_reference: str | None = None,
        authorized_by: EntityId | None = None,
    ) -> Any:
        model = ReleaseDecisionModel(
            id=decision_id.value,
            fund_disposition_id=fund_disposition_id.value,
            decision=decision,
            amount_kobo=amount_kobo,
            currency=currency,
            policy_version=policy_version,
            triggering_fact=triggering_fact,
            evidence_reference=evidence_reference,
            decided_at=decided_at,
            origin=origin,
            authorized_by=authorized_by.value if authorized_by else None,
            reason=reason,
        )
        self._session.add(model)
        await self._session.flush()
        return model


class SqlAlchemyLedgerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        entry_id: EntityId,
        payment_id: EntityId | None,
        fund_disposition_id: EntityId | None,
        entry_type: LedgerEntryType,
        amount_kobo: int,
        currency: str,
        reference_type: str,
        reference_id: EntityId,
        description: str,
        created_at: datetime,
    ) -> Any:
        model = LedgerEntryModel(
            id=entry_id.value,
            payment_id=payment_id.value if payment_id else None,
            fund_disposition_id=fund_disposition_id.value if fund_disposition_id else None,
            entry_type=entry_type.value if hasattr(entry_type, "value") else str(entry_type),
            amount_kobo=amount_kobo,
            currency=currency,
            reference_type=reference_type,
            reference_id=reference_id.value,
            description=description,
            created_at=created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return model

    async def get_by_fund_disposition_id(self, disposition_id: EntityId) -> list[Any]:
        stmt = select(LedgerEntryModel).where(
            LedgerEntryModel.fund_disposition_id == disposition_id.value
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
