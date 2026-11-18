"""Issues task source adapter."""
from __future__ import annotations

from typing import Any
from camp_match.modules.admin_operations.application.ports.outbound import (
    IssueRepository,
    TaskItem,
    TaskSection,
    TaskSource,
)
from camp_match.modules.admin_operations.domain.value_objects import IssueStatus
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.pagination import PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


class IssuesTaskSource(TaskSource):
    def __init__(self, issue_repo: IssueRepository, clock: Any) -> None:
        self._issue_repo = issue_repo
        self._clock = clock

    async def fetch(
        self, actor_id: EntityId, filters: dict[str, Any], limit: int
    ) -> TaskSection:
        now = self._clock.now()
        items = []

        # 1. ISSUES_ASSIGNED_TO_ME
        assigned = await self._issue_repo.list(
            status=IssueStatus.OPEN,
            assignee_id=actor_id,
            page_request=PageRequest(page=1, page_size=limit),
        )
        for issue in assigned.items:
            items.append(
                TaskItem(
                    task_id=f"ISSUES:ISSUE_ASSIGNED_TO_ME:{str(issue.id.value)}",
                    type="ISSUE_ASSIGNED_TO_ME",
                    priority=issue.priority.value,
                    since=issue.created_at,
                    subject={"type": "ISSUE", "id": str(issue.id.value)},
                    target={"type": "ISSUE", "id": str(issue.id.value)}, # Or relevant target
                    facts={
                        "category": issue.category.value,
                        "title": issue.title,
                    },
                    required_permission=Permission.ADMIN_ISSUES_MANAGE.value,
                    can_act=True,
                )
            )

        # 2. ISSUE_UNASSIGNED
        if len(items) < limit:
            unassigned = await self._issue_repo.list(
                status=IssueStatus.OPEN,
                assignee_id=None,
                page_request=PageRequest(page=1, page_size=limit - len(items)),
            )
            for issue in unassigned.items:
                items.append(
                    TaskItem(
                        task_id=f"ISSUES:ISSUE_UNASSIGNED:{str(issue.id.value)}",
                        type="ISSUE_UNASSIGNED",
                        priority=issue.priority.value,
                        since=issue.created_at,
                        subject={"type": "ISSUE", "id": str(issue.id.value)},
                        target={"type": "ISSUE", "id": str(issue.id.value)},
                        facts={
                            "category": issue.category.value,
                            "title": issue.title,
                        },
                        required_permission=Permission.ADMIN_ISSUES_MANAGE.value,
                        can_act=True,
                    )
                )

        return TaskSection(
            source="ISSUES",
            status="OK",
            as_of=now,
            items=items[:limit],
            total=len(items),
        )
