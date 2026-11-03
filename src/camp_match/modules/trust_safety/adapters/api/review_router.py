"""Trust & Safety reviewer and approver API router."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from camp_match.modules.trust_safety.adapters.api import dependencies
from camp_match.modules.trust_safety.adapters.api.schemas import (
    AddNoteSchema,
    AssignCaseSchema,
    ChangeCaseStatusSchema,
    LinkReportSchema,
    PageSchema,
    ProposeEnforcementSchema,
    RecordDecisionSchema,
    RejectEnforcementSchema,
    ReverseEnforcementSchema,
    TriageCaseSchema,
)
from camp_match.modules.trust_safety.application.errors import (
    CaseNotFound,
    CaseStateChanged,
    DuplicateEnforcementAction,
    EnforcementActionNotFound,
    EvidenceNotFound,
    InvalidCaseTransition,
    InvalidDecision,
    InvalidEnforcementRequest,
    InvalidReportSubject,
    ReportAlreadyLinked,
    ReportNotFound,
    SeparationOfDutiesViolation,
    TransitionRequirementNotMet,
)
from camp_match.modules.trust_safety.application.ports.inbound import (
    AddNote,
    AddNoteRequest,
    ApproveEnforcement,
    ApproverCaseView,
    ApproveEnforcementRequest,
    AssignCase,
    AssignCaseRequest,
    ChangeCaseStatus,
    ChangeCaseStatusRequest,
    EvidenceContentView,
    GetCase,
    GetCaseHistory,
    GetCaseHistoryRequest,
    GetCaseRequest,
    LinkReportToCase,
    LinkReportToCaseRequest,
    ListCases,
    ListCasesRequest,
    ListReviewQueue,
    ListReviewQueueRequest,
    OpenCaseFromReport,
    OpenCaseFromReportRequest,
    ProposeEnforcement,
    ProposeEnforcementRequest,
    RecordDecision,
    RecordDecisionRequest,
    RejectEnforcement,
    RejectEnforcementRequest,
    ReverseEnforcement,
    ReverseEnforcementRequest,
    ReviewerCaseView,
    ReviewerReportView,
    TriageCase,
    TriageCaseRequest,
    ViewEvidence,
    ViewEvidenceRequest,
)
from camp_match.modules.trust_safety.domain.value_objects import CasePriority, CaseStatus, ReportCategory
from camp_match.platform.security.authentication import get_current_identity_id
from camp_match.shared_kernel.application.errors import (
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from camp_match.shared_kernel.application.pagination import PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/safety/review", tags=["Trust & Safety Review"])


def _handle_error(e: Exception) -> None:
    if isinstance(e, (CaseNotFound, ReportNotFound, EvidenceNotFound, NotFoundError, EnforcementActionNotFound)):
        raise HTTPException(status_code=404, detail="Resource not found.") from e
    if isinstance(e, (ForbiddenError, SeparationOfDutiesViolation)):
        raise HTTPException(status_code=403, detail=str(e)) from e
    if isinstance(e, (InvalidCaseTransition, CaseStateChanged, ReportAlreadyLinked, DuplicateEnforcementAction, InvalidDecision, TransitionRequirementNotMet)):
        raise HTTPException(status_code=409, detail=str(e)) from e
    if isinstance(e, (ValidationError, InvalidReportSubject, InvalidEnforcementRequest)):
        raise HTTPException(status_code=422, detail=str(e)) from e
    raise e


@router.get("/reports", response_model=PageSchema[ReviewerReportView])
async def list_review_queue(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    list_uc: Annotated[ListReviewQueue, Depends(dependencies.get_list_review_queue_use_case)],
    category: ReportCategory | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PageSchema[ReviewerReportView]:
    try:
        req = ListReviewQueueRequest(
            actor_id=actor_id,
            category=category,
            page_request=PageRequest(page=page, page_size=page_size),
        )
        paged = await list_uc.execute(req)
        return PageSchema(
            items=list(paged.items),
            total=paged.total,
            page=paged.page,
            page_size=paged.page_size,
        )
    except Exception as e:
        _handle_error(e)
        raise


@router.post("/reports/{report_id}/open-case", status_code=status.HTTP_201_CREATED)
async def open_case_from_report(
    report_id: UUID,
    body: TriageCaseSchema,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    open_uc: Annotated[OpenCaseFromReport, Depends(dependencies.get_open_case_from_report_use_case)],
) -> dict[str, str]:
    try:
        req = OpenCaseFromReportRequest(
            actor_id=actor_id,
            report_id=EntityId(report_id),
            priority=body.priority,
        )
        case_id = await open_uc.execute(req)
        return {"case_id": str(case_id.value)}
    except Exception as e:
        _handle_error(e)
        raise


@router.get("/cases", response_model=PageSchema[ReviewerCaseView])
async def list_cases(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    list_uc: Annotated[ListCases, Depends(dependencies.get_list_cases_use_case)],
    status_filter: CaseStatus | None = Query(None, alias="status"),
    category: ReportCategory | None = None,
    assigned_to: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PageSchema[ReviewerCaseView]:
    try:
        req = ListCasesRequest(
            actor_id=actor_id,
            status=status_filter,
            category=category,
            assigned_to=EntityId(assigned_to) if assigned_to else None,
            page_request=PageRequest(page=page, page_size=page_size),
        )
        paged = await list_uc.execute(req)
        return PageSchema(
            items=list(paged.items),
            total=paged.total,
            page=paged.page,
            page_size=paged.page_size,
        )
    except Exception as e:
        _handle_error(e)
        raise


@router.get("/cases/{case_id}")
async def get_case(
    case_id: UUID,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    get_uc: Annotated[GetCase, Depends(dependencies.get_get_case_use_case)],
) -> ReviewerCaseView | ApproverCaseView:
    try:
        req = GetCaseRequest(
            actor_id=actor_id,
            case_id=EntityId(case_id),
        )
        return await get_uc.execute(req)
    except Exception as e:
        _handle_error(e)
        raise


@router.post("/cases/{case_id}/reports", status_code=status.HTTP_204_NO_CONTENT)
async def link_report_to_case(
    case_id: UUID,
    body: LinkReportSchema,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    link_uc: Annotated[LinkReportToCase, Depends(dependencies.get_link_report_to_case_use_case)],
) -> None:
    try:
        req = LinkReportToCaseRequest(
            actor_id=actor_id,
            case_id=EntityId(case_id),
            report_id=EntityId(body.report_id),
        )
        await link_uc.execute(req)
    except Exception as e:
        _handle_error(e)


@router.post("/cases/{case_id}/triage", status_code=status.HTTP_204_NO_CONTENT)
async def triage_case(
    case_id: UUID,
    body: TriageCaseSchema,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    triage_uc: Annotated[TriageCase, Depends(dependencies.get_triage_case_use_case)],
) -> None:
    try:
        req = TriageCaseRequest(
            actor_id=actor_id,
            case_id=EntityId(case_id),
            priority=body.priority,
        )
        await triage_uc.execute(req)
    except Exception as e:
        _handle_error(e)


@router.post("/cases/{case_id}/assign", status_code=status.HTTP_204_NO_CONTENT)
async def assign_case(
    case_id: UUID,
    body: AssignCaseSchema,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    assign_uc: Annotated[AssignCase, Depends(dependencies.get_assign_case_use_case)],
) -> None:
    try:
        req = AssignCaseRequest(
            actor_id=actor_id,
            case_id=EntityId(case_id),
            assignee_id=EntityId(body.assignee_id) if body.assignee_id else None,
        )
        await assign_uc.execute(req)
    except Exception as e:
        _handle_error(e)


@router.post("/cases/{case_id}/status", status_code=status.HTTP_204_NO_CONTENT)
async def change_case_status(
    case_id: UUID,
    body: ChangeCaseStatusSchema,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    status_uc: Annotated[ChangeCaseStatus, Depends(dependencies.get_change_case_status_use_case)],
) -> None:
    try:
        req = ChangeCaseStatusRequest(
            actor_id=actor_id,
            case_id=EntityId(case_id),
            target_status=body.to_status,
        )
        await status_uc.execute(req)
    except Exception as e:
        _handle_error(e)


@router.get("/cases/{case_id}/evidence/{evidence_id}", response_model=EvidenceContentView)
async def view_evidence(
    case_id: UUID,
    evidence_id: UUID,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    view_uc: Annotated[ViewEvidence, Depends(dependencies.get_view_evidence_use_case)],
) -> EvidenceContentView:
    try:
        req = ViewEvidenceRequest(
            actor_id=actor_id,
            evidence_id=EntityId(evidence_id),
        )
        return await view_uc.execute(req)
    except Exception as e:
        _handle_error(e)
        raise


@router.post("/cases/{case_id}/notes", status_code=status.HTTP_201_CREATED)
async def add_note(
    case_id: UUID,
    body: AddNoteSchema,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    note_uc: Annotated[AddNote, Depends(dependencies.get_add_note_use_case)],
) -> dict[str, str]:
    try:
        req = AddNoteRequest(
            actor_id=actor_id,
            case_id=EntityId(case_id),
            kind=body.kind,
            content=body.content,
            cited_evidence_ids=tuple(EntityId(eid) for eid in body.cited_evidence_ids),
            corrects_note_id=EntityId(body.corrects_note_id) if body.corrects_note_id else None,
        )
        note_id = await note_uc.execute(req)
        return {"note_id": str(note_id.value)}
    except Exception as e:
        _handle_error(e)
        raise


@router.get("/cases/{case_id}/history", response_model=list[Any])
async def get_case_history(
    case_id: UUID,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    history_uc: Annotated[GetCaseHistory, Depends(dependencies.get_get_case_history_use_case)],
) -> list[Any]:
    try:
        req = GetCaseHistoryRequest(
            actor_id=actor_id,
            case_id=EntityId(case_id),
        )
        return list(await history_uc.execute(req))
    except Exception as e:
        _handle_error(e)
        raise


@router.post("/cases/{case_id}/decisions", status_code=status.HTTP_201_CREATED)
async def record_decision(
    case_id: UUID,
    body: RecordDecisionSchema,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    decision_uc: Annotated[RecordDecision, Depends(dependencies.get_record_decision_use_case)],
) -> dict[str, str]:
    try:
        req = RecordDecisionRequest(
            actor_id=actor_id,
            case_id=EntityId(case_id),
            decision_type=body.decision_type,
            rationale=body.rationale,
            cited_evidence_ids=tuple(EntityId(eid) for eid in body.cited_evidence_ids),
            cited_note_ids=tuple(EntityId(nid) for nid in body.cited_note_ids),
        )
        dec_id = await decision_uc.execute(req)
        return {"decision_id": str(dec_id.value)}
    except Exception as e:
        _handle_error(e)
        raise


@router.post("/cases/{case_id}/enforcement", status_code=status.HTTP_201_CREATED)
async def propose_enforcement(
    case_id: UUID,
    body: ProposeEnforcementSchema,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    prop_uc: Annotated[ProposeEnforcement, Depends(dependencies.get_propose_enforcement_use_case)],
) -> dict[str, str]:
    try:
        req = ProposeEnforcementRequest(
            actor_id=actor_id,
            case_id=EntityId(case_id),
            decision_id=EntityId(body.decision_id),
            action_type=body.action_type,
            target_user_id=EntityId(body.target_user_id) if body.target_user_id else None,
            target_listing_id=EntityId(body.target_listing_id) if body.target_listing_id else None,
            ends_at=body.ends_at,
            rationale=body.rationale,
        )
        enf_id = await prop_uc.execute(req)
        return {"enforcement_id": str(enf_id.value)}
    except Exception as e:
        _handle_error(e)
        raise


@router.post("/enforcement/{action_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def approve_enforcement(
    action_id: UUID,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    app_uc: Annotated[ApproveEnforcement, Depends(dependencies.get_approve_enforcement_use_case)],
) -> None:
    try:
        req = ApproveEnforcementRequest(
            actor_id=actor_id,
            enforcement_id=EntityId(action_id),
        )
        await app_uc.execute(req)
    except Exception as e:
        _handle_error(e)


@router.post("/enforcement/{action_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_enforcement(
    action_id: UUID,
    body: RejectEnforcementSchema,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    rej_uc: Annotated[RejectEnforcement, Depends(dependencies.get_reject_enforcement_use_case)],
) -> None:
    try:
        req = RejectEnforcementRequest(
            actor_id=actor_id,
            enforcement_id=EntityId(action_id),
            reason=body.reason,
        )
        await rej_uc.execute(req)
    except Exception as e:
        _handle_error(e)


@router.post("/enforcement/{action_id}/reverse", status_code=status.HTTP_204_NO_CONTENT)
async def reverse_enforcement(
    action_id: UUID,
    body: ReverseEnforcementSchema,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    rev_uc: Annotated[ReverseEnforcement, Depends(dependencies.get_reverse_enforcement_use_case)],
) -> None:
    try:
        req = ReverseEnforcementRequest(
            actor_id=actor_id,
            enforcement_id=EntityId(action_id),
            reason=body.reason,
        )
        await rev_uc.execute(req)
    except Exception as e:
        _handle_error(e)
