from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from camp_match.modules.security.application.errors import SecurityForbiddenError
from camp_match.modules.security.domain.value_objects import Permission


@dataclass(frozen=True)
class ReviewerOverview:
    reports_awaiting_triage: int
    open_cases_by_status: dict[str, int]
    high_or_urgent_open_cases: int


@dataclass(frozen=True)
class ApproverOverview:
    enforcement_awaiting_approval: int
    enforcement_retrying: int
    enforcement_failed: int


@dataclass(frozen=True)
class SafetyOverview:
    reviewer: ReviewerOverview | None
    approver: ApproverOverview | None


class GetSafetyOverviewUseCase:
    def __init__(
        self,
        report_repo: Any,
        case_repo: Any,
        enforcement_repo: Any,
        auth_service: Any,
    ) -> None:
        self._report_repo = report_repo
        self._case_repo = case_repo
        self._enforcement_repo = enforcement_repo
        self._auth = auth_service

    async def execute(self, actor_id: Any) -> SafetyOverview:
        has_reviewer = False
        has_approver = False

        try:
            await self._auth.authorize(actor_id, Permission.SAFETY_CASE_REVIEW)
            has_reviewer = True
        except Exception:
            pass

        try:
            await self._auth.authorize(actor_id, Permission.SAFETY_ENFORCEMENT_APPROVE)
            has_approver = True
        except Exception:
            pass

        if not has_reviewer and not has_approver:
            raise SecurityForbiddenError(
                "Action requires SAFETY_CASE_REVIEW or SAFETY_ENFORCEMENT_APPROVE permission."
            )

        reviewer_data = None
        if has_reviewer:
            reports_awaiting = await self._report_repo.count_reports_awaiting_triage()
            cases_by_status = await self._case_repo.count_cases_by_status()
            high_urgent = await self._case_repo.count_high_or_urgent_open_cases()
            reviewer_data = ReviewerOverview(
                reports_awaiting_triage=reports_awaiting,
                open_cases_by_status=cases_by_status,
                high_or_urgent_open_cases=high_urgent,
            )

        approver_data = None
        if has_approver:
            awaiting_approval = (
                await self._enforcement_repo.count_enforcement_awaiting_approval()
            )
            retrying = await self._enforcement_repo.count_enforcement_retrying()
            failed = await self._enforcement_repo.count_enforcement_failed()
            approver_data = ApproverOverview(
                enforcement_awaiting_approval=awaiting_approval,
                enforcement_retrying=retrying,
                enforcement_failed=failed,
            )

        return SafetyOverview(reviewer=reviewer_data, approver=approver_data)
