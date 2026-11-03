"""View evidence use case for Trust & Safety."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from camp_match.modules.security.domain.value_objects import Permission
from camp_match.modules.trust_safety.application.errors import EvidenceNotFound
from camp_match.modules.trust_safety.application.ports.inbound import (
    EvidenceContentView,
    ViewEvidenceRequest,
)
from camp_match.modules.trust_safety.application.ports.outbound import (
    CaseRepository,
    EvidenceRepository,
    ReportRepository,
)
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId


class ViewEvidenceUseCase:
    def __init__(
        self,
        case_repo: CaseRepository,
        evidence_repo: EvidenceRepository,
        report_repo: ReportRepository,
        case_access: CaseAccess,
        authorization_service: Any,
        unit_of_work: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._case_repo = case_repo
        self._evidence_repo = evidence_repo
        self._report_repo = report_repo
        self._case_access = case_access
        self._auth = authorization_service
        self._uow = unit_of_work
        self._clock = clock

    async def execute(self, request: ViewEvidenceRequest) -> EvidenceContentView:
        await self._auth.authorize(request.actor_id, Permission.SAFETY_CASE_REVIEW)
        await self._auth.authorize(request.actor_id, Permission.SAFETY_EVIDENCE_VIEW)

        evidence = await self._evidence_repo.get_by_id(request.evidence_id)
        if not evidence:
            raise EvidenceNotFound("Evidence not found.")

        report = await self._report_repo.get_by_id(evidence.report_id)
        if not report:
            raise EvidenceNotFound("Evidence report not found.")

        case_id = getattr(report, "case_id", None)
        if not case_id and hasattr(self._case_repo, "get_case_id_for_report"):
            case_id = await self._case_repo.get_case_id_for_report(report.id)
        if not case_id:
            case_id = getattr(evidence, "case_id", None)

        if not case_id:
            raise EvidenceNotFound("Evidence is not linked to a case.")

        await self._case_access.require_reviewer(request.actor_id, case_id)

        if evidence.snapshot and evidence.content_sha256:
            canonical = json.dumps(evidence.snapshot, sort_keys=True, separators=(",", ":"))
            computed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if computed != evidence.content_sha256:
                pass  # Hash mismatch handling if needed

        async with self._uow:
            await self._case_repo.add_event(
                case_id=case_id,
                report_id=report.id,
                event_type="EVIDENCE_VIEWED",
                actor_id=request.actor_id,
                details={"evidence_id": str(evidence.id)},
            )
            await self._uow.commit()

        return EvidenceContentView(
            id=evidence.id,
            report_id=evidence.report_id,
            evidence_type=evidence.evidence_type,
            resource_type=evidence.resource_type,
            resource_id=evidence.resource_id,
            collected_by=evidence.collected_by,
            collected_at=evidence.collected_at,
            source=evidence.source,
            confidentiality=evidence.confidentiality,
            conversation_id=evidence.conversation_id,
            snapshot=evidence.snapshot,
            content_sha256=evidence.content_sha256,
        )
