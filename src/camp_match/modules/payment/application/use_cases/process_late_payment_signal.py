from __future__ import annotations

import structlog

from camp_match.modules.payment.application.ports.outbound import BookingProvider
from camp_match.modules.payment.application.use_cases.execute_refund import ExecuteRefundUseCase
from camp_match.modules.payment.application.use_cases.verify_payment_attempt import (
    VerifyPaymentAttemptUseCase,
)
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class ProcessLatePaymentSignalUseCase:
    def __init__(
        self,
        booking_provider: BookingProvider,
        verify_attempt_use_case: VerifyPaymentAttemptUseCase,
        execute_refund_use_case: ExecuteRefundUseCase,
        clock: Clock,
    ) -> None:
        self.booking_provider = booking_provider
        self.verify_attempt_use_case = verify_attempt_use_case
        self.execute_refund_use_case = execute_refund_use_case
        self.clock = clock

    async def execute(
        self,
        attempt_id: EntityId,
        booking_id: EntityId,
        provider_reference: str,
        fund_disposition_id: EntityId | None,
        amount_money,
    ) -> str:
        booking = await self.booking_provider.get_booking(booking_id)
        if not booking or booking.status == "CANCELLED":
            if fund_disposition_id:
                await self.execute_refund_use_case.execute(
                    decision_id=EntityId.new(),
                    fund_disposition_id=fund_disposition_id,
                    amount=amount_money,
                    provider_reference=provider_reference,
                )
                logger.warning(
                    "late_payment_automatic_refund_executed",
                    booking_id=booking_id,
                    attempt_id=attempt_id,
                )
                return "REFUNDED"
        else:
            await self.verify_attempt_use_case.execute(attempt_id, provider_reference)
            logger.warning(
                "late_payment_verified_and_confirmed",
                booking_id=booking_id,
                attempt_id=attempt_id,
            )
            return "CONFIRMED"
        return "SKIPPED"
