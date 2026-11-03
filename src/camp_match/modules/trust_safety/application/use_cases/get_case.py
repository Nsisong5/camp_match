"""Get case use case for Trust & Safety."""
from __future__ import annotations

from typing import Any

from camp_match.modules.security.domain.value_objects import Permission
from camp_match.modules.trust_safety.application.errors import ForbiddenError
from camp_match.modules.trust_safety.application.ports.inbound import (
    ApproverCaseView,
    DecisionView,
    EnforcementView,
    EvidenceMetadataView,
    GetCaseRequest,
    NoteView,
    ReviewerCaseView,
    ReviewerReportView,
)
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess


class GetCaseUseCase:
    def __init__(
        self,
        case_repo: Any,
        report_repo: Any,
        evidence_repo: Any,
        note_repo: Any,
        decision_repo: Any,
        enforcement_repo: Any,
        case_access: CaseAccess,
        auth_service: Any,
    ) -> None:
        self._case_repo = case_repo
        self._report_repo = report_repo
        self._evidence_repo = evidence_repo
        self._note_repo = note_repo
        self._decision_repo = decision_repo
        self._enforcement_repo = enforcement_repo
        self._case_access = case_access
        self._auth = auth_service

    async def execute(self, request: GetCaseRequest) -> ReviewerCaseView | ApproverCaseView:
        is_approver = False
        is_reviewer = False
        try:
            await self._auth.authorize(request.actor_id, Permission.SAFETY_ENFORCEMENT_APPROVE)
            is_approver = True
        except Exception:
            pass

        try:
            await self._auth.authorize(request.actor_id, Permission.SAFETY_CASE_REVIEW)
            is_reviewer = True
        except Exception:
            pass

        if not is_approver and not is_reviewer:
            raise ForbiddenError("Not authorized to view case.")

        if is_approver and not is_reviewer:
            case = await self._case_access.require_approver(request.actor_id, request.case_id)
        else:
            case = await self._case_access.require_reviewer(request.actor_id, request.case_id)

        decisions = await self._decision_repo.list_by_case_id(case.id)
        enforcements = await self._enforcement_repo.list_by_case_id(case.id)

        decision_views = tuple(
            DecisionView(
                id=d.id,
                case_id=d.case_id,
                decision_type=d.decision_type,
                rationale=d.rationale,
                decided_by=d.decided_by,
                decided_at=d.decided_at,
            )
            for d in decisions
        )
        enforcement_views = tuple(
            EnforcementView(
                id=e.id,
                case_id=e.case_id,
                decision_id=e.decision_id,
                action_type=e.action_type,
                target_user_id=e.target_user_id,
                target_listing_id=e.target_listing_id,
                target_key=e.target_key,
                ends_at=e.ends_at,
                status=e.status,
                rationale=e.rationale,
                proposed_by=e.proposed_by,
                proposed_at=e.proposed_at,
                approved_by=e.approved_by,
                approved_at=e.approved_at,
                rejected_reason=e.rejected_reason,
                applied_at=e.applied_at,
                reversed_by=e.reversed_by,
                reversal_reason=e.reversal_reason,
                reversed_at=e.reversed_at,
            )
            for e in enforcements
        )

        if is_approver and not is_reviewer:
            return ApproverCaseView(
                id=case.id,
                category=case.category,
                priority=case.priority,
                status=case.status,
                subject_user_id=case.subject_user_id,
                assigned_to=case.assigned_to,
                version=case.version,
                cycle=case.cycle,
                created_by=case.created_by,
                created_at=case.created_at,
                updated_at=case.updated_at,
                resolved_at=case.resolved_at,
                closed_at=case.closed_at,
                decisions=decision_views,
                enforcement_actions=enforcement_views,
            )

        reports = await self._report_repo.list_by_case_id(case.id)
        evidence = await self._evidence_repo.list_by_case_id(case.id)
        notes = await self._note_repo.list_by_case_id(case.id)

        report_views = tuple(
            ReviewerReportView(
                id=r.id,
                reporter_id=r.reporter_id,
                category=r.category,
                subject_type=r.subject_type,
                subject_id=r.subject_id,
                description=r.description.value,
                status=r.status,
                case_id=case.id,
                similar_report_count=0,
                created_at=r.created_at,
            )
            for r in reports
        )
        evidence_meta_views = tuple(
            EvidenceMetadataView(
                id=ev.id,
                report_id=ev.report_id,
                evidence_type=ev.evidence_type,
                resource_type=ev.resource_type,
                resource_id=ev.resource_id,
                collected_by=ev.collected_by,
                collected_at=ev.collected_at,
                source=ev.source,
                confidentiality=ev.confidentiality,
            )
            for ev in evidence
        )
        note_views = tuple(
            NoteView(
                id=n.id,
                case_id=n.case_id,
                author_id=n.author_id,
                kind=n.kind,
                content=n.content,
                corrects_note_id=n.corrects_note_id,
                created_at=n.created_at,
            )
            for n in notes
        )

        return ReviewerCaseView(
            id=case.id,
            category=case.category,
            priority=case.priority,
            status=case.status,
            subject_user_id=case.subject_user_id,
            assigned_to=case.assigned_to,
            version=case.version,
            cycle=case.cycle,
            created_by=case.created_by,
            created_at=case.created_at,
            updated_at=case.updated_at,
            resolved_at=case.resolved_at,
            closed_at=case.closed_at,
            linked_reports=report_views,
            evidence_metadata=evidence_meta_views,
            notes=note_views,
            decisions=decision_views,
            enforcement_actions=enforcement_views,
            viewer_kind="REVIEWER",
        )
