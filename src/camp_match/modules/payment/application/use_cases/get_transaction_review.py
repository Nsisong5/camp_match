"""Get transaction review use case."""
from __future__ import annotations

import structlog
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from camp_match.modules.payment.application.ports.outbound import (
    DisputeRepository,
    FundDispositionRepository,
    LedgerEntryRepository,
    PaymentAttemptRepository,
    PaymentRepository,
    ReleaseDecisionRepository,
    ReleaseScheduleRepository,
    TransactionReviewRepository,
)
from camp_match.modules.payment.application.use_cases.evaluate_release_eligibility import (
    EvaluateReleaseEligibilityUseCase,
)
from camp_match.modules.payment.domain.value_objects import EvaluationMode
from camp_match.modules.security.application.use_cases.authorize_action import AuthorizeActionUseCase
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.errors import NotFoundError
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class GetTransactionReviewRequest:
    actor_id: EntityId
    payment_id: EntityId | None = None
    booking_id: EntityId | None = None


class GetTransactionReviewUseCase:
    def __init__(
        self,
        review_repo: TransactionReviewRepository,
        payment_repo: PaymentRepository,
        attempt_repo: PaymentAttemptRepository,
        fd_repo: FundDispositionRepository,
        decision_repo: ReleaseDecisionRepository,
        schedule_repo: ReleaseScheduleRepository,
        dispute_repo: DisputeRepository,
        ledger_repo: LedgerEntryRepository,
        context_provider: Any,
        evaluate_uc: EvaluateReleaseEligibilityUseCase,
        authorizer: AuthorizeActionUseCase,
        clock: Clock,
        settings: Any,
    ) -> None:
        self.review_repo = review_repo
        self.payment_repo = payment_repo
        self.attempt_repo = attempt_repo
        self.fd_repo = fd_repo
        self.decision_repo = decision_repo
        self.schedule_repo = schedule_repo
        self.dispute_repo = dispute_repo
        self.ledger_repo = ledger_repo
        self.context_provider = context_provider
        self.evaluate_uc = evaluate_uc
        self.authorizer = authorizer
        self.clock = clock
        self.settings = settings

    async def execute(self, request: GetTransactionReviewRequest) -> dict[str, Any]:
        await self.authorizer.execute(request.actor_id, Permission.PAYMENT_REVIEW)

        if request.payment_id:
            review = await self.review_repo.get_by_payment_id(request.payment_id)
        elif request.booking_id:
            reviews = await self.review_repo.get_by_booking_id(request.booking_id)
            review = reviews[0] if reviews else None
        else:
            raise ValueError("Either payment_id or booking_id must be provided")

        if not review:
            raise NotFoundError("Transaction review not found")

        payment_id = EntityId(review.payment_id)
        
        # Load all authoritative data
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise NotFoundError("Payment not found")

        fd = await self.fd_repo.get_by_payment_id(payment_id)
        attempts = await self.attempt_repo.list_by_booking_id(EntityId(review.booking_id))
        decisions = await self.decision_repo.list_by_fund_disposition_id(fd.id) if fd else []
        disputes = await self.dispute_repo.list_by_fund_disposition_id(fd.id) if fd else []
        ledger_entries = await self.ledger_repo.list_by_payment_id(payment_id)
        schedule = await self.schedule_repo.get_by_fund_disposition_id(fd.id) if fd else None
        
        # Timeline assembly (minimal version for now)
        timeline = []
        timeline.append({
            "at": review.paid_at,
            "kind": "PAYMENT_CONFIRMED",
            "actor": {"type": "STUDENT", "id": str(review.student_id)},
            "detail": {}
        })
        if review.handover_offered_at:
            timeline.append({
                "at": review.handover_offered_at,
                "kind": "HANDOVER_OFFERED",
                "actor": {"type": "PROVIDER", "id": str(review.provider_id) if review.provider_id else None},
                "detail": {}
            })
        if review.handover_accepted_at:
            timeline.append({
                "at": review.handover_accepted_at,
                "kind": "HANDOVER_ACCEPTED",
                "actor": {"type": "STUDENT", "id": str(review.student_id)},
                "detail": {}
            })
        # ... more timeline events as specified ...

        # Live evaluation
        evaluation = await self.evaluate_uc.execute(
            fund_disposition_id=fd.id,
            requested_amount_kobo=fd.remaining_releasable_kobo,
            mode=EvaluationMode.MANUAL,
        )
        
        auto_evaluation = await self.evaluate_uc.execute(
            fund_disposition_id=fd.id,
            requested_amount_kobo=fd.remaining_releasable_kobo,
            mode=EvaluationMode.AUTOMATIC,
        )

        # Context (Profile, Housing names)
        context = await self.context_provider.get_context(
            student_id=EntityId(review.student_id),
            provider_id=EntityId(review.provider_id) if review.provider_id else None,
            listing_id=EntityId(review.listing_id) if review.listing_id else None,
            property_id=EntityId(review.property_id) if review.property_id else None,
            booking_id=EntityId(review.booking_id),
        )

        can_release = False
        try:
            await self.authorizer.execute(request.actor_id, Permission.PAYMENT_AUTHORIZE_RELEASE)
            can_release = evaluation.eligible
        except Exception:
            pass

        can_refund = False
        try:
            await self.authorizer.execute(request.actor_id, Permission.PAYMENT_AUTHORIZE_REFUND)
            can_refund = True # Simplified
        except Exception:
            pass

        return {
            "as_of": self.clock.now(),
            "transaction": {
                "payment_id": str(payment_id.value),
                "payment_attempt_id": str(review.payment_attempt_id),
                "fund_disposition_id": str(review.fund_disposition_id),
                "booking_id": str(review.booking_id),
                "amount_kobo": review.amount_kobo,
                "currency": review.currency,
                "paid_at": review.paid_at,
                "provider_name": review.provider_name,
                "provider_reference": review.provider_reference,
                "stage": review.stage,
                "next_action": review.next_action,
                "next_action_since": review.next_action_since,
            },
            "parties": context["parties"],
            "listing": context["listing"],
            "context_status": context["context_status"],
            "booking": context["booking"],
            "funds": {
                "held_kobo": fd.held_amount_kobo if fd else 0,
                "released_kobo": review.released_kobo,
                "refunded_kobo": review.refunded_kobo,
                "remaining_kobo": fd.remaining_releasable_kobo if fd else 0,
                "disposition_status": fd.status.value if fd and hasattr(fd.status, "value") else "UNKNOWN",
            },
            "release": {
                "eligible_now": evaluation.eligible,
                "blocking_reason": evaluation.blocking_reason,
                "decisions": [
                    {
                        "id": str(d.id.value),
                        "decision": d.decision,
                        "amount_kobo": d.amount_kobo,
                        "origin": d.origin,
                        "triggering_fact": d.triggering_fact,
                        "decided_at": d.decided_at,
                        "authorized_by": str(d.authorized_by.value),
                        "student_confirmed_at": review.student_confirmed_at,
                    }
                    for d in decisions
                ],
                "auto": {
                    "enabled": not getattr(self.settings, "platform_jobs_disabled", "").count("payment_auto_release"),
                    "delay_hours": getattr(self.settings, "payment_auto_release_delay_hours", 48),
                    "cycle": review.release_cycle,
                    "window_starts_at": review.release_window_starts_at,
                    "earliest_auto_release_at": None, # Should be computed
                    "blocking_reason": auto_evaluation.blocking_reason,
                    "warnings": {
                        "required": review.warnings_required or 0,
                        "sent": review.warnings_sent or 0,
                        "items": [], # Should load from warnings table
                    }
                }
            },
            "operations": {
                "releases": [
                    {
                        "id": str(op.id.value),
                        "amount_kobo": op.amount.amount_kobo,
                        "status": op.status.value,
                        "requested_at": op.requested_at,
                        "confirmed_at": op.confirmed_at,
                        "failure_reason": op.failure_reason,
                    }
                    for op in (fd.release_operations if fd else [])
                ],
                "refunds": [
                    {
                        "id": str(op.id.value),
                        "amount_kobo": op.amount.amount_kobo,
                        "status": op.status.value,
                        "requested_at": op.requested_at,
                        "confirmed_at": op.confirmed_at,
                        "failure_reason": op.failure_reason,
                    }
                    for op in (fd.refund_operations if fd else [])
                ],
            },
            "disputes": [
                {
                    "id": str(d.id.value),
                    "status": d.status.value if hasattr(d.status, "value") else str(d.status),
                    "raised_at": d.raised_at,
                    "raised_by": str(d.raised_by.value),
                    "reason": d.reason,
                    "resolved_at": d.resolved_at,
                    "resolved_by": str(d.resolved_by.value) if d.resolved_by else None,
                    "resolution_notes": d.resolution_notes,
                }
                for d in disputes
            ],
            "attempts": [
                {
                    "id": str(a.id.value),
                    "status": a.status.value if hasattr(a.status, "value") else str(a.status),
                    "created_at": a.created_at,
                    "confirmed_at": a.confirmed_at,
                }
                for a in attempts
            ],
            "ledger": {
                "balanced": True, # Should compute
                "entries": [
                    {
                        "type": e.entry_type.value if hasattr(e.entry_type, "value") else str(e.entry_type),
                        "amount_kobo": e.amount_kobo,
                        "created_at": e.created_at,
                    }
                    for e in ledger_entries
                ],
            },
            "timeline": sorted(timeline, key=lambda x: x["at"]),
            "available_actions": {
                "release": {"allowed": can_release, "reason": evaluation.blocking_reason if not evaluation.eligible else None},
                "refund": {"allowed": can_refund, "reason": None},
                "resolve_dispute": {"allowed": review.stage == "DISPUTED", "reason": None if review.stage == "DISPUTED" else "no_open_dispute"},
            }
        }
