from __future__ import annotations

from typing import Annotated, Any
from datetime import datetime, date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form

from camp_match.modules.verification.adapters.api import dependencies, schemas
from camp_match.modules.verification.application.ports.inbound import (
    CreateVerificationCaseRequest,
    SubmitVerificationCaseRequest,
    AddEvidenceRequest,
    ReviewEvidenceRequest,
    GetEvidenceAccessRequest,
    AssignInspectorRequest,
    StartInspectionRequest,
    RecordInspectionObservationRequest,
    CompleteInspectionRequest,
    StartReviewRequest,
    RequestInspectionRequest,
    MarkReadyForDecisionRequest,
    ApproveVerificationRequest,
    RejectVerificationRequest,
    RevokeVerificationRequest,
    GetVerificationCaseRequest,
    GetVerificationStatusRequest,
    ListMyVerificationCasesRequest,
    ListMyInspectionsRequest,
    ListPendingReviewsRequest,
)
from camp_match.modules.verification.application.use_cases.create_verification_case import CreateVerificationCaseUseCase
from camp_match.modules.verification.application.use_cases.submit_verification_case import SubmitVerificationCaseUseCase
from camp_match.modules.verification.application.use_cases.add_evidence import AddEvidenceUseCase
from camp_match.modules.verification.application.use_cases.review_evidence import ReviewEvidenceUseCase
from camp_match.modules.verification.application.use_cases.get_evidence_access import GetEvidenceAccessUseCase
from camp_match.modules.verification.application.use_cases.assign_inspector import AssignInspectorUseCase
from camp_match.modules.verification.application.use_cases.start_inspection import StartInspectionUseCase
from camp_match.modules.verification.application.use_cases.record_inspection_observation import RecordInspectionObservationUseCase
from camp_match.modules.verification.application.use_cases.complete_inspection import CompleteInspectionUseCase
from camp_match.modules.verification.application.use_cases.start_review import StartReviewUseCase
from camp_match.modules.verification.application.use_cases.request_inspection import RequestInspectionUseCase
from camp_match.modules.verification.application.use_cases.mark_ready_for_decision import MarkReadyForDecisionUseCase
from camp_match.modules.verification.application.use_cases.approve_verification import ApproveVerificationUseCase
from camp_match.modules.verification.application.use_cases.reject_verification import RejectVerificationUseCase
from camp_match.modules.verification.application.use_cases.revoke_verification import RevokeVerificationUseCase
from camp_match.modules.verification.application.use_cases.get_verification_case import GetVerificationCaseUseCase
from camp_match.modules.verification.application.use_cases.get_verification_status import GetVerificationStatusUseCase
from camp_match.modules.verification.application.use_cases.list_my_verification_cases import ListMyVerificationCasesUseCase
from camp_match.modules.verification.application.use_cases.list_my_inspections import ListMyInspectionsUseCase
from camp_match.modules.verification.application.use_cases.list_pending_reviews import ListPendingReviewsUseCase

from camp_match.modules.verification.application.errors import (
    VerificationCaseNotFound,
    EvidenceNotFound,
    InspectionNotFound,
    InvalidVerificationTransition,
    EvidenceRequirementNotSatisfied,
    DecisionNotAllowed,
    VerificationForbiddenError,
)
from camp_match.modules.verification.domain.value_objects import VerificationTargetType, EvidenceType, ChecklistItem
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.modules.verification.application.ports.outbound import AuthorizationService
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.platform.security.authentication import get_current_identity_id
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/verification", tags=["verification"])
public_router = APIRouter(prefix="/api/v1", tags=["verification-status"])


@router.post("/cases", status_code=status.HTTP_201_CREATED)
async def create_verification_case(
    data: schemas.CreateVerificationCaseSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    housing_provider=Depends(dependencies.get_housing_provider),
    history_repo=Depends(dependencies.get_history_repo),
    uow: UnitOfWork = Depends(dependencies.get_uow),
    auth_service: AuthorizationService = Depends(dependencies.get_auth_service),
) -> dict:
    # Authorization handled inside use case (ownership resolved)
    use_case = CreateVerificationCaseUseCase(case_repo, housing_provider, history_repo, uow)
    try:
        response = await use_case.execute(
            CreateVerificationCaseRequest(
                target_type=data.target_type,
                target_id=EntityId(data.target_id),
                caller_id=identity_id,
            )
        )
        return {"case_id": str(response.case_id.value)}
    except (VerificationCaseNotFound, InvalidVerificationTransition) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except VerificationForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/cases/{case_id}/submit", status_code=status.HTTP_200_OK)
async def submit_verification_case(
    case_id: str,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    history_repo=Depends(dependencies.get_history_repo),
    uow: UnitOfWork = Depends(dependencies.get_uow),
) -> dict:
    use_case = SubmitVerificationCaseUseCase(case_repo, history_repo, uow)
    try:
        cid = EntityId.from_string(case_id)
        await use_case.execute(SubmitVerificationCaseRequest(case_id=cid, caller_id=identity_id))
    except VerificationCaseNotFound:
        raise HTTPException(status_code=404, detail="Verification case not found")
    except VerificationForbiddenError:
        raise HTTPException(status_code=403, detail="Forbidden")
    except InvalidVerificationTransition as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"status": "submitted"}


@router.post("/cases/{case_id}/evidence", status_code=status.HTTP_201_CREATED)
async def add_evidence(
    case_id: str,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    evidence_repo=Depends(dependencies.get_evidence_repo),
    inspection_repo=Depends(dependencies.get_inspection_repo),
    history_repo=Depends(dependencies.get_history_repo),
    media_provider=Depends(dependencies.get_media_provider),
    uow: UnitOfWork = Depends(dependencies.get_uow),
    evidence_type: EvidenceType = Form(...),
    file: UploadFile = File(...),
    source_description: str | None = Form(None),
    captured_at: datetime | None = Form(None),
) -> dict:
    use_case = AddEvidenceUseCase(case_repo, evidence_repo, inspection_repo, history_repo, media_provider, uow)
    try:
        cid = EntityId.from_string(case_id)
        content = await file.read()
        resp = await use_case.execute(
            AddEvidenceRequest(
                case_id=cid,
                evidence_type=evidence_type,
                content=content,
                content_type=file.content_type or "application/octet-stream",
                source_description=source_description,
                captured_at=captured_at,
                caller_id=identity_id,
            )
        )
        return {"evidence_id": str(resp.evidence_id.value)}
    except VerificationCaseNotFound:
        raise HTTPException(status_code=404, detail="Verification case not found")
    except VerificationForbiddenError:
        raise HTTPException(status_code=403, detail="Forbidden")
    except InvalidVerificationTransition as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/cases/{case_id}", status_code=status.HTTP_200_OK)
async def get_verification_case(
    case_id: str,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    evidence_repo=Depends(dependencies.get_evidence_repo),
    inspection_repo=Depends(dependencies.get_inspection_repo),
    history_repo=Depends(dependencies.get_history_repo),
    auth_service: AuthorizationService = Depends(dependencies.get_auth_service),
) -> Any:
    use_case = GetVerificationCaseUseCase(case_repo, evidence_repo, inspection_repo, history_repo)
    try:
        cid = EntityId.from_string(case_id)
        is_reviewer = False
        try:
            await auth_service.authorize(identity_id, Permission.VERIFICATION_REVIEW)
            is_reviewer = True
        except Exception:
            pass

        result = await use_case.execute(
            GetVerificationCaseRequest(case_id=cid, caller_id=identity_id, is_reviewer=is_reviewer)
        )
        return result
    except VerificationCaseNotFound:
        raise HTTPException(status_code=404, detail="Verification case not found")
    except VerificationForbiddenError:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/cases/mine", status_code=status.HTTP_200_OK)
async def list_my_verification_cases(
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
) -> list:
    use_case = ListMyVerificationCasesUseCase(case_repo)
    return await use_case.execute(ListMyVerificationCasesRequest(caller_id=identity_id))


@router.post("/cases/{case_id}/start-review", status_code=status.HTTP_200_OK)
async def start_review(
    case_id: str,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    history_repo=Depends(dependencies.get_history_repo),
    uow: UnitOfWork = Depends(dependencies.get_uow),
    auth_service: AuthorizationService = Depends(dependencies.get_auth_service),
) -> dict:
    await auth_service.authorize(identity_id, Permission.VERIFICATION_REVIEW)
    use_case = StartReviewUseCase(case_repo, history_repo, uow)
    try:
        cid = EntityId.from_string(case_id)
        await use_case.execute(StartReviewRequest(case_id=cid, caller_id=identity_id))
        return {"status": "under_review"}
    except VerificationCaseNotFound:
        raise HTTPException(status_code=404, detail="Verification case not found")
    except InvalidVerificationTransition as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/cases/{case_id}/request-inspection", status_code=status.HTTP_200_OK)
async def request_inspection(
    case_id: str,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    history_repo=Depends(dependencies.get_history_repo),
    uow: UnitOfWork = Depends(dependencies.get_uow),
    auth_service: AuthorizationService = Depends(dependencies.get_auth_service),
) -> dict:
    await auth_service.authorize(identity_id, Permission.VERIFICATION_REVIEW)
    use_case = RequestInspectionUseCase(case_repo, history_repo, uow)
    try:
        cid = EntityId.from_string(case_id)
        await use_case.execute(RequestInspectionRequest(case_id=cid, caller_id=identity_id))
        return {"status": "inspection_required"}
    except VerificationCaseNotFound:
        raise HTTPException(status_code=404, detail="Verification case not found")
    except InvalidVerificationTransition as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/cases/{case_id}/assign-inspector", status_code=status.HTTP_201_CREATED)
async def assign_inspector(
    case_id: str,
    data: schemas.AssignInspectorSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    inspection_repo=Depends(dependencies.get_inspection_repo),
    history_repo=Depends(dependencies.get_history_repo),
    uow: UnitOfWork = Depends(dependencies.get_uow),
    auth_service: AuthorizationService = Depends(dependencies.get_auth_service),
) -> dict:
    await auth_service.authorize(identity_id, Permission.VERIFICATION_REVIEW)
    use_case = AssignInspectorUseCase(case_repo, inspection_repo, history_repo, uow)
    try:
        cid = EntityId.from_string(case_id)
        inspector_id = EntityId(data.inspector_id)
        resp = await use_case.execute(
            AssignInspectorRequest(case_id=cid, inspector_id=inspector_id, caller_id=identity_id)
        )
        return {"inspection_id": str(resp.inspection_id.value)}
    except VerificationCaseNotFound:
        raise HTTPException(status_code=404, detail="Verification case not found")
    except InvalidVerificationTransition as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/cases/{case_id}/ready-for-decision", status_code=status.HTTP_200_OK)
async def mark_ready_for_decision(
    case_id: str,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    history_repo=Depends(dependencies.get_history_repo),
    uow: UnitOfWork = Depends(dependencies.get_uow),
    auth_service: AuthorizationService = Depends(dependencies.get_auth_service),
) -> dict:
    await auth_service.authorize(identity_id, Permission.VERIFICATION_REVIEW)
    use_case = MarkReadyForDecisionUseCase(case_repo, history_repo, uow)
    try:
        cid = EntityId.from_string(case_id)
        await use_case.execute(MarkReadyForDecisionRequest(case_id=cid, caller_id=identity_id))
        return {"status": "decision_pending"}
    except VerificationCaseNotFound:
        raise HTTPException(status_code=404, detail="Verification case not found")
    except InvalidVerificationTransition as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/cases/{case_id}/approve", status_code=status.HTTP_200_OK)
async def approve_verification(
    case_id: str,
    data: schemas.DecisionSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    evidence_repo=Depends(dependencies.get_evidence_repo),
    inspection_repo=Depends(dependencies.get_inspection_repo),
    decision_repo=Depends(dependencies.get_decision_repo),
    history_repo=Depends(dependencies.get_history_repo),
    uow: UnitOfWork = Depends(dependencies.get_uow),
    auth_service: AuthorizationService = Depends(dependencies.get_auth_service),
) -> dict:
    await auth_service.authorize(identity_id, Permission.VERIFICATION_REVIEW)
    use_case = ApproveVerificationUseCase(case_repo, evidence_repo, inspection_repo, decision_repo, history_repo, uow)
    try:
        cid = EntityId.from_string(case_id)
        resp = await use_case.execute(
            ApproveVerificationRequest(case_id=cid, reason=data.reason, caller_id=identity_id)
        )
        return {"status": "verified", "expires_at": resp.expires_at.isoformat()}
    except VerificationCaseNotFound:
        raise HTTPException(status_code=404, detail="Verification case not found")
    except VerificationForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except (EvidenceRequirementNotSatisfied, InvalidVerificationTransition) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DecisionNotAllowed as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/cases/{case_id}/reject", status_code=status.HTTP_200_OK)
async def reject_verification(
    case_id: str,
    data: schemas.DecisionSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    decision_repo=Depends(dependencies.get_decision_repo),
    history_repo=Depends(dependencies.get_history_repo),
    uow: UnitOfWork = Depends(dependencies.get_uow),
    auth_service: AuthorizationService = Depends(dependencies.get_auth_service),
) -> dict:
    await auth_service.authorize(identity_id, Permission.VERIFICATION_REVIEW)
    use_case = RejectVerificationUseCase(case_repo, decision_repo, history_repo, uow)
    try:
        cid = EntityId.from_string(case_id)
        await use_case.execute(
            RejectVerificationRequest(case_id=cid, reason=data.reason, caller_id=identity_id)
        )
        return {"status": "rejected"}
    except VerificationCaseNotFound:
        raise HTTPException(status_code=404, detail="Verification case not found")
    except InvalidVerificationTransition as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DecisionNotAllowed as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/cases/{case_id}/revoke", status_code=status.HTTP_200_OK)
async def revoke_verification(
    case_id: str,
    data: schemas.RevokeSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    history_repo=Depends(dependencies.get_history_repo),
    uow: UnitOfWork = Depends(dependencies.get_uow),
    auth_service: AuthorizationService = Depends(dependencies.get_auth_service),
) -> dict:
    await auth_service.authorize(identity_id, Permission.VERIFICATION_REVIEW)
    use_case = RevokeVerificationUseCase(case_repo, history_repo, uow)
    try:
        cid = EntityId.from_string(case_id)
        await use_case.execute(
            RevokeVerificationRequest(case_id=cid, revocation_reason=data.revocation_reason, caller_id=identity_id)
        )
        return {"status": "revoked"}
    except VerificationCaseNotFound:
        raise HTTPException(status_code=404, detail="Verification case not found")
    except InvalidVerificationTransition as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/reviews/pending", status_code=status.HTTP_200_OK)
async def list_pending_reviews(
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    auth_service: AuthorizationService = Depends(dependencies.get_auth_service),
) -> list:
    await auth_service.authorize(identity_id, Permission.VERIFICATION_REVIEW)
    use_case = ListPendingReviewsUseCase(case_repo, is_reviewer=True)
    return await use_case.execute(ListPendingReviewsRequest(caller_id=identity_id))


@router.get("/inspections/mine", status_code=status.HTTP_200_OK)
async def list_my_inspections(
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    inspection_repo=Depends(dependencies.get_inspection_repo),
) -> list:
    use_case = ListMyInspectionsUseCase(inspection_repo)
    return await use_case.execute(ListMyInspectionsRequest(caller_id=identity_id))


@router.post("/inspections/{inspection_id}/start", status_code=status.HTTP_200_OK)
async def start_inspection(
    inspection_id: str,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    inspection_repo=Depends(dependencies.get_inspection_repo),
    history_repo=Depends(dependencies.get_history_repo),
    uow: UnitOfWork = Depends(dependencies.get_uow),
) -> dict:
    use_case = StartInspectionUseCase(inspection_repo, history_repo, uow)
    try:
        iid = EntityId.from_string(inspection_id)
        await use_case.execute(StartInspectionRequest(inspection_id=iid, caller_id=identity_id))
        return {"status": "in_progress"}
    except InspectionNotFound:
        raise HTTPException(status_code=404, detail="Inspection not found")
    except VerificationForbiddenError:
        raise HTTPException(status_code=403, detail="Forbidden")
    except InvalidVerificationTransition as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/inspections/{inspection_id}/observations", status_code=status.HTTP_201_CREATED)
async def record_observation(
    inspection_id: str,
    data: schemas.RecordObservationSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    inspection_repo=Depends(dependencies.get_inspection_repo),
    observation_repo=Depends(dependencies.get_observation_repo),
    history_repo=Depends(dependencies.get_history_repo),
    uow: UnitOfWork = Depends(dependencies.get_uow),
) -> dict:
    use_case = RecordInspectionObservationUseCase(inspection_repo, observation_repo, history_repo, uow)
    try:
        iid = EntityId.from_string(inspection_id)
        resp = await use_case.execute(
            RecordInspectionObservationRequest(
                inspection_id=iid,
                item=data.item,
                passed=data.passed,
                notes=data.notes,
                caller_id=identity_id,
            )
        )
        return {"observation_id": str(resp.observation_id.value)}
    except InspectionNotFound:
        raise HTTPException(status_code=404, detail="Inspection not found")
    except VerificationForbiddenError:
        raise HTTPException(status_code=403, detail="Forbidden")
    except InvalidVerificationTransition as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/inspections/{inspection_id}/complete", status_code=status.HTTP_200_OK)
async def complete_inspection(
    inspection_id: str,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    inspection_repo=Depends(dependencies.get_inspection_repo),
    observation_repo=Depends(dependencies.get_observation_repo),
    case_repo=Depends(dependencies.get_verification_case_repo),
    history_repo=Depends(dependencies.get_history_repo),
    uow: UnitOfWork = Depends(dependencies.get_uow),
) -> dict:
    use_case = CompleteInspectionUseCase(inspection_repo, observation_repo, case_repo, history_repo, uow)
    try:
        iid = EntityId.from_string(inspection_id)
        resp = await use_case.execute(CompleteInspectionRequest(inspection_id=iid, caller_id=identity_id))
        return {"inspection_id": str(resp.inspection_id.value), "result": resp.result.value}
    except InspectionNotFound:
        raise HTTPException(status_code=404, detail="Inspection not found")
    except VerificationForbiddenError:
        raise HTTPException(status_code=403, detail="Forbidden")
    except InvalidVerificationTransition as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/evidence/{evidence_id}/review", status_code=status.HTTP_200_OK)
async def review_evidence(
    evidence_id: str,
    data: schemas.ReviewEvidenceSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    evidence_repo=Depends(dependencies.get_evidence_repo),
    history_repo=Depends(dependencies.get_history_repo),
    uow: UnitOfWork = Depends(dependencies.get_uow),
    auth_service: AuthorizationService = Depends(dependencies.get_auth_service),
) -> dict:
    await auth_service.authorize(identity_id, Permission.VERIFICATION_REVIEW)
    use_case = ReviewEvidenceUseCase(case_repo, evidence_repo, history_repo, uow)
    try:
        eid = EntityId.from_string(evidence_id)
        resp = await use_case.execute(
            ReviewEvidenceRequest(
                evidence_id=eid,
                review_status=data.review_status,
                notes=data.notes,
                caller_id=identity_id,
            )
        )
        return {"evidence_id": str(resp.evidence_id.value), "review_status": resp.review_status.value}
    except EvidenceNotFound:
        raise HTTPException(status_code=404, detail="Evidence not found")
    except VerificationCaseNotFound:
        raise HTTPException(status_code=404, detail="Verification case not found")
    except InvalidVerificationTransition as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/evidence/{evidence_id}/access", status_code=status.HTTP_200_OK)
async def get_evidence_access(
    evidence_id: str,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    evidence_repo=Depends(dependencies.get_evidence_repo),
    inspection_repo=Depends(dependencies.get_inspection_repo),
    history_repo=Depends(dependencies.get_history_repo),
    media_provider=Depends(dependencies.get_media_provider),
    uow: UnitOfWork = Depends(dependencies.get_uow),
    auth_service: AuthorizationService = Depends(dependencies.get_auth_service),
) -> dict:
    try:
        eid = EntityId.from_string(evidence_id)
        is_reviewer = False
        try:
            await auth_service.authorize(identity_id, Permission.VERIFICATION_REVIEW)
            is_reviewer = True
        except Exception:
            pass

        use_case = GetEvidenceAccessUseCase(
            case_repo, evidence_repo, inspection_repo, history_repo, media_provider, uow, is_reviewer=is_reviewer
        )
        grant = await use_case.execute(GetEvidenceAccessRequest(evidence_id=eid, caller_id=identity_id))
        return {"token": grant.token, "expires_at": grant.expires_at.isoformat()}
    except EvidenceNotFound:
        raise HTTPException(status_code=404, detail="Evidence not found")
    except VerificationForbiddenError:
        raise HTTPException(status_code=403, detail="Forbidden")


@public_router.get("/verification-status/{target_type}/{target_id}", status_code=status.HTTP_200_OK)
async def get_verification_status(
    target_type: VerificationTargetType,
    target_id: UUID,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    case_repo=Depends(dependencies.get_verification_case_repo),
    decision_repo=Depends(dependencies.get_decision_repo),
) -> schemas.VerificationStatusResponseSchema:
    use_case = GetVerificationStatusUseCase(case_repo, decision_repo)
    resp = await use_case.execute(
        GetVerificationStatusRequest(target_type=target_type, target_id=EntityId(target_id))
    )
    return schemas.VerificationStatusResponseSchema(
        is_verified=resp.is_verified,
        verified_on=resp.verified_on,
    )
