from __future__ import annotations

from datetime import timedelta

import structlog

from camp_match.modules.payment.application.ports.outbound import PaymentAttemptRepository
from camp_match.modules.payment.application.use_cases.verify_payment_attempt import (
    VerifyPaymentAttemptUseCase,
)
from camp_match.modules.payment.domain.value_objects import PaymentAttemptStatus
from camp_match.shared_kernel.domain.clock import Clock

logger = structlog.get_logger()


class ReprocessUncertainAttemptsUseCase:
    def __init__(
        self,
        attempt_repo: PaymentAttemptRepository,
        verify_attempt_use_case: VerifyPaymentAttemptUseCase,
        staleness_minutes: int,
        clock: Clock,
    ) -> None:
        self.attempt_repo = attempt_repo
        self.verify_attempt_use_case = verify_attempt_use_case
        self.staleness_minutes = staleness_minutes
        self.clock = clock

    async def execute(self, pending_attempts: list) -> int:
        now = self.clock.now()
        threshold = now - timedelta(minutes=self.staleness_minutes)
        reprocessed = 0

        for attempt in pending_attempts:
            if attempt.status == PaymentAttemptStatus.PENDING and attempt.created_at <= threshold:
                if attempt.provider_reference:
                    try:
                        await self.verify_attempt_use_case.execute(attempt.id, attempt.provider_reference)
                        reprocessed += 1
                    except Exception as e:
                        logger.warning("reprocess_attempt_failed", attempt_id=attempt.id, error=str(e))

        logger.info("reprocess_uncertain_attempts_completed", reprocessed=reprocessed)
        return reprocessed
