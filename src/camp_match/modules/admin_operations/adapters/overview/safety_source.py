from __future__ import annotations

from typing import Any

from camp_match.shared_kernel.domain.identifiers import EntityId


class SafetySourceAdapter:
    def __init__(self, get_safety_overview_uc: Any) -> None:
        self._uc = get_safety_overview_uc

    async def fetch(self, actor_id: EntityId) -> dict[str, Any]:
        overview = await self._uc.execute(actor_id)
        reviewer_dict = None
        if overview.reviewer:
            reviewer_dict = {
                "reports_awaiting_triage": overview.reviewer.reports_awaiting_triage,
                "open_cases_by_status": overview.reviewer.open_cases_by_status,
                "high_or_urgent_open_cases": overview.reviewer.high_or_urgent_open_cases,
            }
        approver_dict = None
        if overview.approver:
            approver_dict = {
                "enforcement_awaiting_approval": overview.approver.enforcement_awaiting_approval,
                "enforcement_retrying": overview.approver.enforcement_retrying,
                "enforcement_failed": overview.approver.enforcement_failed,
            }
        return {"reviewer": reviewer_dict, "approver": approver_dict}
