from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from camp_match.modules.admin_operations.adapters.api import dependencies, schemas
from camp_match.modules.admin_operations.application.errors import IdempotencyKeyConflict
from camp_match.modules.admin_operations.application.ports.inbound import IssueDetailView, IssueView
from camp_match.modules.admin_operations.application.use_cases.assign_issue import (
    AssignIssueUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.change_issue_status import (
    ChangeIssueStatusUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.create_issue import (
    CreateIssueUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.disable_account import (
    DisableAccountUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.get_account import (
    GetAccountUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.get_issue import (
    GetIssueUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.get_overview import (
    GetOverviewUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.grant_staff_role import (
    GrantStaffRoleUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.list_audit_events import (
    ListAuditEventsUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.list_issues import (
    ListIssuesUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.list_staff import (
    ListStaffUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.reactivate_account import (
    ReactivateAccountUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.requeue_dead_notification_events import (
    RequeueDeadNotificationEventsUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.requeue_failed_safety_enforcement import (
    RequeueFailedSafetyEnforcementUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.revoke_staff_role import (
    RevokeStaffRoleUseCase,
)
from camp_match.modules.admin_operations.domain.value_objects import (
    AdminActionType,
    IssueCategory,
    IssuePriority,
    IssueStatus,
)
from camp_match.platform.security.authentication import get_current_identity_id
from camp_match.shared_kernel.application.pagination import PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Operations"])


@router.get("/overview", response_model=schemas.OverviewViewSchema)
async def get_overview(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    uc: Annotated[GetOverviewUseCase, Depends(dependencies.get_overview_use_case)],
) -> Any:
    return await uc.execute(actor_id)


@router.get("/operations/issues", response_model=schemas.PageSchema[schemas.IssueViewSchema])
async def list_issues(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    uc: Annotated[ListIssuesUseCase, Depends(dependencies.get_list_issues_use_case)],
    status: IssueStatus | None = Query(None),
    assignee_id: UUID | None = Query(None),
    priority: IssuePriority | None = Query(None),
    category: IssueCategory | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Any:
    return await uc.execute(
        actor_id,
        status=status,
        assignee_id=EntityId(assignee_id) if assignee_id else None,
        priority=priority,
        category=category,
        page_request=PageRequest(page=page, page_size=page_size),
    )


def _to_issue_schema(v: IssueView) -> schemas.IssueViewSchema:
    return schemas.IssueViewSchema(
        id=v.id.value,
        category=v.category,
        title=v.title,
        description=v.description,
        priority=v.priority,
        status=v.status,
        assignee_id=v.assignee_id.value if v.assignee_id else None,
        references=[(cast(Any, r[0].value if hasattr(r[0], "value") else r[0]), r[1].value) for r in v.references],
        created_by=v.created_by.value,
        idempotency_key=v.idempotency_key,
        version=v.version,
        created_at=v.created_at,
        updated_at=v.updated_at,
        resolved_at=v.resolved_at,
        resolution_summary=v.resolution_summary,
    )


@router.post("/operations/issues", response_model=schemas.IssueViewSchema)
async def create_issue(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    body: schemas.CreateIssueSchema,
    uc: Annotated[CreateIssueUseCase, Depends(dependencies.get_create_issue_use_case)],
    issue_repo: Annotated[Any, Depends(dependencies.get_issue_repo)],
    response: Response,
) -> Any:
    refs = tuple((r[0], EntityId(r[1])) for r in body.references)
    try:
        result = await uc.execute(
            actor_id=actor_id,
            category=body.category,
            title=body.title,
            description=body.description,
            priority=body.priority,
            references=refs,
            idempotency_key=body.idempotency_key,
        )
        response.status_code = status.HTTP_201_CREATED
        return _to_issue_schema(result)
    except IdempotencyKeyConflict:
        existing = await issue_repo.get_by_idempotency(actor_id, body.idempotency_key)
        if existing:
            response.status_code = status.HTTP_200_OK
            existing_view = IssueView(
                id=existing.id,
                category=existing.category,
                title=existing.title,
                description=existing.description,
                priority=existing.priority,
                status=existing.status,
                assignee_id=existing.assignee_id,
                references=existing.references,
                created_by=existing.created_by,
                idempotency_key=existing.idempotency_key,
                version=existing.version,
                created_at=existing.created_at,
                updated_at=existing.updated_at,
                resolved_at=existing.resolved_at,
                resolution_summary=existing.resolution_summary,
            )
            return _to_issue_schema(existing_view)
        raise


def _to_issue_detail_schema(v: IssueDetailView) -> schemas.IssueDetailViewSchema:
    return schemas.IssueDetailViewSchema(
        issue=_to_issue_schema(v.issue),
        history=[
            schemas.IssueEventViewSchema(
                id=e.id.value,
                issue_id=e.issue_id.value,
                event_type=e.event_type,
                actor_id=e.actor_id.value,
                occurred_at=e.occurred_at,
                details=e.details,
            )
            for e in v.history
        ],
    )


@router.get("/operations/issues/{issue_id}", response_model=schemas.IssueDetailViewSchema)
async def get_issue(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    issue_id: UUID,
    uc: Annotated[GetIssueUseCase, Depends(dependencies.get_get_issue_use_case)],
) -> Any:
    result = await uc.execute(actor_id, EntityId(issue_id))
    return _to_issue_detail_schema(result)


@router.post("/operations/issues/{issue_id}/assign", response_model=schemas.IssueViewSchema)
async def assign_issue(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    issue_id: UUID,
    body: schemas.AssignIssueSchema,
    uc: Annotated[AssignIssueUseCase, Depends(dependencies.get_assign_issue_use_case)],
) -> Any:
    result = await uc.execute(
        actor_id=actor_id,
        issue_id=EntityId(issue_id),
        assignee_id=EntityId(body.assignee_id) if body.assignee_id else None,
        version=body.version,
    )
    return _to_issue_schema(result)


@router.post("/operations/issues/{issue_id}/resolve", response_model=schemas.IssueViewSchema)
async def resolve_issue(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    issue_id: UUID,
    body: schemas.ResolveIssueSchema,
    uc: Annotated[ChangeIssueStatusUseCase, Depends(dependencies.get_change_issue_status_use_case)],
) -> Any:
    result = await uc.execute(
        actor_id,
        EntityId(issue_id),
        IssueStatus.RESOLVED,
        body.version,
        resolution_summary=body.resolution_summary,
    )
    return _to_issue_schema(result)


@router.post("/operations/issues/{issue_id}/status", response_model=schemas.IssueViewSchema)
async def change_issue_status(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    issue_id: UUID,
    body: schemas.ChangeStatusSchema,
    uc: Annotated[ChangeIssueStatusUseCase, Depends(dependencies.get_change_issue_status_use_case)],
) -> Any:
    result = await uc.execute(
        actor_id,
        EntityId(issue_id),
        body.to_status,
        body.version,
        reason=body.reason,
        resolution_summary=body.resolution_summary,
    )
    return _to_issue_schema(result)


@router.get("/audit-events", response_model=schemas.PageSchema[schemas.AuditEventViewSchema])
async def list_audit_events(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    uc: Annotated[ListAuditEventsUseCase, Depends(dependencies.get_list_audit_events_use_case)],
    actor_filter_id: UUID | None = Query(None),
    action_type: AdminActionType | None = Query(None),
    target_id: UUID | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Any:
    return await uc.execute(
        actor_id,
        actor_filter_id=EntityId(actor_filter_id) if actor_filter_id else None,
        action_type=action_type,
        target_id=EntityId(target_id) if target_id else None,
        from_date=from_date,
        to_date=to_date,
        page_request=PageRequest(page=page, page_size=page_size),
    )


@router.get("/accounts/{identity_id}", response_model=schemas.AccountViewSchema)
async def get_account(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    identity_id: UUID,
    uc: Annotated[GetAccountUseCase, Depends(dependencies.get_get_account_use_case)],
) -> Any:
    return await uc.execute(actor_id, EntityId(identity_id))


@router.post("/accounts/{identity_id}/disable", response_model=schemas.AccountViewSchema)
async def disable_account(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    identity_id: UUID,
    body: schemas.ReasonSchema,
    uc: Annotated[DisableAccountUseCase, Depends(dependencies.get_disable_account_use_case)],
) -> Any:
    return await uc.execute(actor_id, EntityId(identity_id), body.reason)


@router.post("/accounts/{identity_id}/reactivate", response_model=schemas.AccountViewSchema)
async def reactivate_account(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    identity_id: UUID,
    body: schemas.ReasonSchema,
    uc: Annotated[ReactivateAccountUseCase, Depends(dependencies.get_reactivate_account_use_case)],
) -> Any:
    return await uc.execute(actor_id, EntityId(identity_id), body.reason)


@router.get("/staff", response_model=schemas.PageSchema[schemas.StaffViewSchema])
async def list_staff(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    uc: Annotated[ListStaffUseCase, Depends(dependencies.get_list_staff_use_case)],
    role: str = Query("OPERATIONS"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Any:
    return await uc.execute(actor_id, role, PageRequest(page=page, page_size=page_size))


@router.post("/staff/{identity_id}/roles", response_model=schemas.StaffViewSchema)
async def grant_staff_role(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    identity_id: UUID,
    body: schemas.GrantRoleSchema,
    uc: Annotated[GrantStaffRoleUseCase, Depends(dependencies.get_grant_staff_role_use_case)],
) -> Any:
    return await uc.execute(actor_id, EntityId(identity_id), body.role, body.reason)


@router.post("/staff/{identity_id}/roles/{role}/revoke", response_model=schemas.StaffViewSchema)
async def revoke_staff_role(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    identity_id: UUID,
    role: str,
    body: schemas.ReasonSchema,
    uc: Annotated[RevokeStaffRoleUseCase, Depends(dependencies.get_revoke_staff_role_use_case)],
) -> Any:
    return await uc.execute(actor_id, EntityId(identity_id), role, body.reason)


@router.post("/recovery/notification-events/requeue-dead", response_model=schemas.RecoveryResultSchema)
async def requeue_dead_notifications(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    body: schemas.ReasonSchema,
    uc: Annotated[
        RequeueDeadNotificationEventsUseCase,
        Depends(dependencies.get_requeue_dead_notification_events_use_case),
    ],
) -> Any:
    return await uc.execute(actor_id, body.reason)


@router.post("/recovery/safety-enforcement/requeue-failed", response_model=schemas.RecoveryResultSchema)
async def requeue_failed_safety(
    actor_id: Annotated[EntityId, Depends(get_current_identity_id)],
    body: schemas.ReasonSchema,
    uc: Annotated[
        RequeueFailedSafetyEnforcementUseCase,
        Depends(dependencies.get_requeue_failed_safety_enforcement_use_case),
    ],
) -> Any:
    return await uc.execute(actor_id, body.reason)
