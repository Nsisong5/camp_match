"""Trust & Safety reporter API router."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from camp_match.modules.trust_safety.adapters.api import dependencies
from camp_match.modules.trust_safety.adapters.api.schemas import (
    PageSchema,
    ReportAckResponse,
    ReportCreateRequest,
    ReporterReportResponse,
)
from camp_match.modules.trust_safety.application.errors import (
    DuplicateOpenReport,
    IdempotencyKeyConflict,
    ReportRateLimitExceeded,
)
from camp_match.modules.trust_safety.application.ports.inbound import (
    GetMyReport,
    GetMyReportRequest,
    ListMyReports,
    ListMyReportsRequest,
    SubmitReport,
    SubmitReportRequest,
)
from camp_match.modules.trust_safety.domain.value_objects import SubjectType
from camp_match.platform.security.authentication import get_current_identity_id
from camp_match.shared_kernel.application.errors import (
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from camp_match.shared_kernel.application.pagination import PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/safety", tags=["Trust & Safety"])


@router.post("/reports", response_model=ReportAckResponse, status_code=status.HTTP_201_CREATED)
async def submit_report(
    body: ReportCreateRequest,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    submit_uc: Annotated[SubmitReport, Depends(dependencies.get_submit_report_use_case)],
    response: Response,
) -> ReportAckResponse:
    sub_type = SubjectType(body.subject.type)
    subject_id = EntityId(body.subject.id)
    conv_id = None
    msg_id = None

    if sub_type == SubjectType.CONVERSATION:
        conv_id = subject_id
        if hasattr(body.subject, "message_ids") and body.subject.message_ids:
            msg_id = EntityId(body.subject.message_ids[0])

    req = SubmitReportRequest(
        actor_id=actor_id,
        category=body.category,
        subject_type=sub_type,
        subject_id=subject_id,
        description=body.description,
        idempotency_key=body.idempotency_key,
        conversation_id=conv_id,
        message_id=msg_id,
    )

    try:
        ack = await submit_uc.execute(req)
        if ack.replayed:
            response.status_code = status.HTTP_200_OK
        return ReportAckResponse(
            report_id=ack.report_id.value,
            status=ack.status,
            created_at=ack.created_at,
            replayed=ack.replayed,
        )
    except ReportRateLimitExceeded as e:
        headers = {}
        if e.retry_after_seconds is not None:
            headers["Retry-After"] = str(e.retry_after_seconds)
        raise HTTPException(status_code=429, detail=str(e), headers=headers) from e
    except (DuplicateOpenReport, IdempotencyKeyConflict) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/reports/mine", response_model=PageSchema[ReporterReportResponse])
async def list_my_reports(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    list_uc: Annotated[ListMyReports, Depends(dependencies.get_list_my_reports_use_case)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PageSchema[ReporterReportResponse]:
    req = ListMyReportsRequest(
        actor_id=actor_id,
        page_request=PageRequest(page=page, page_size=page_size),
    )
    try:
        paged = await list_uc.execute(req)
        items = [
            ReporterReportResponse(
                id=item.id.value,
                category=item.category,
                subject_type=item.subject_type,
                subject_id=item.subject_id.value,
                description=item.description,
                status=item.status,
                created_at=item.created_at,
            )
            for item in paged.items
        ]
        return PageSchema(
            items=items,
            total=paged.total,
            page=paged.page,
            page_size=paged.page_size,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.get("/reports/{report_id}", response_model=ReporterReportResponse)
async def get_my_report(
    report_id: UUID,
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    get_uc: Annotated[GetMyReport, Depends(dependencies.get_get_my_report_use_case)],
) -> ReporterReportResponse:
    req = GetMyReportRequest(
        actor_id=actor_id,
        report_id=EntityId(report_id),
    )
    try:
        item = await get_uc.execute(req)
        return ReporterReportResponse(
            id=item.id.value,
            category=item.category,
            subject_type=item.subject_type,
            subject_id=item.subject_id.value,
            description=item.description,
            status=item.status,
            created_at=item.created_at,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Report not found.") from e
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
