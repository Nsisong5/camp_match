"""Case access service for Trust & Safety (Chunk 10)."""
from __future__ import annotations

from typing import Any

from camp_match.modules.trust_safety.application.errors import CaseNotFound
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId


class CaseAccess:
    def __init__(
        self,
        case_repo: Any,
        report_repo: Any,
        authorization_service: Any,
    ) -> None:
        self._case_repo = case_repo
        self._report_repo = report_repo
        self._auth = authorization_service

    async def require_reviewer(self, actor_id: EntityId, case_id: EntityId) -> Any:
        await self._auth.authorize(actor_id, Permission.SAFETY_CASE_REVIEW)
        case = await self._case_repo.get_by_id(case_id)
        if not case:
            raise CaseNotFound("Case not found.")

        if case.subject_user_id == actor_id:
            raise CaseNotFound("Case not found.")

        linked_reports = await self._report_repo.list_by_case_id(case_id) if hasattr(self._report_repo, "list_by_case_id") else []
        for r in linked_reports:
            if r.reporter_id == actor_id:
                raise CaseNotFound("Case not found.")

        return case

    async def require_approver(self, actor_id: EntityId, case_id: EntityId) -> Any:
        await self._auth.authorize(actor_id, Permission.SAFETY_ENFORCEMENT_APPROVE)
        case = await self._case_repo.get_by_id(case_id)
        if not case:
            raise CaseNotFound("Case not found.")

        if case.subject_user_id == actor_id:
            raise CaseNotFound("Case not found.")

        linked_reports = await self._report_repo.list_by_case_id(case_id) if hasattr(self._report_repo, "list_by_case_id") else []
        for r in linked_reports:
            if r.reporter_id == actor_id:
                raise CaseNotFound("Case not found.")

        return case
