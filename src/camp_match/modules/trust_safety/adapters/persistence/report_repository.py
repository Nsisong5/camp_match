"""SQLAlchemy Report Repository adapter."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from camp_match.modules.trust_safety.adapters.persistence.models import (
    SafetyCaseReportModel,
    SafetyReportModel,
)
from camp_match.modules.trust_safety.application.errors import (
    DuplicateOpenReport,
    IdempotencyKeyConflict,
)
from camp_match.modules.trust_safety.domain.entities import Report
from camp_match.modules.trust_safety.domain.value_objects import (
    ReportCategory,
    ReportDescription,
    ReportStatus,
    SubjectType,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId


def _to_domain(m: SafetyReportModel) -> Report:
    return Report(
        id=EntityId(m.id),
        reporter_id=EntityId(m.reporter_id),
        category=ReportCategory(m.category),
        subject_type=SubjectType(m.subject_type),
        subject_id=EntityId(m.subject_id),
        subject_user_id=EntityId(m.subject_user_id),
        description=ReportDescription(m.description),
        status=ReportStatus(m.status),
        idempotency_key=m.idempotency_key,
        request_fingerprint=m.request_fingerprint,
        created_at=m.created_at,
    )


class SqlAlchemyReportRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def add(self, report: Report) -> None:
        model = SafetyReportModel(
            id=report.id.value,
            reporter_id=report.reporter_id.value,
            category=report.category.value,
            subject_type=report.subject_type.value,
            subject_id=report.subject_id.value,
            subject_user_id=report.subject_user_id.value,
            description=report.description.value,
            status=report.status.value,
            idempotency_key=report.idempotency_key,
            request_fingerprint=report.request_fingerprint,
            created_at=report.created_at,
        )
        self.session.add(model)
        try:
            await self.session.flush()
        except IntegrityError as e:
            await self.session.rollback()
            err_str = str(e.orig).lower()
            if "uq_safety_reporter_idempotency" in err_str:
                raise IdempotencyKeyConflict("Report idempotency key already exists for this reporter.") from e
            if "uq_safety_duplicate_open_report" in err_str:
                # Find existing open report ID for this reporter and subject/category
                stmt = select(SafetyReportModel.id).where(
                    SafetyReportModel.reporter_id == report.reporter_id.value,
                    SafetyReportModel.subject_type == report.subject_type.value,
                    SafetyReportModel.subject_id == report.subject_id.value,
                    SafetyReportModel.category == report.category.value,
                    SafetyReportModel.status != "CLOSED",
                )
                res = await self.session.execute(stmt)
                existing_id = res.scalar_one_or_none()
                if existing_id:
                    raise DuplicateOpenReport(existing_report_id=EntityId(existing_id)) from e
                raise DuplicateOpenReport(existing_report_id=report.id) from e
            raise

    async def get_by_id(self, report_id: EntityId) -> Report | None:
        res = await self.session.get(SafetyReportModel, report_id.value)
        return _to_domain(res) if res else None

    async def get_by_idempotency_key(
        self, reporter_id: EntityId, idempotency_key: str
    ) -> Report | None:
        stmt = select(SafetyReportModel).where(
            SafetyReportModel.reporter_id == reporter_id.value,
            SafetyReportModel.idempotency_key == idempotency_key,
        )
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        return _to_domain(m) if m else None

    async def list_by_reporter(self, reporter_id: EntityId, page_request: PageRequest) -> Page[Report]:
        base_stmt = select(SafetyReportModel).where(SafetyReportModel.reporter_id == reporter_id.value)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        offset = (page_request.page - 1) * page_request.page_size
        stmt = (
            base_stmt.order_by(SafetyReportModel.created_at.desc())
            .offset(offset)
            .limit(page_request.page_size)
        )
        res = await self.session.execute(stmt)
        items = [_to_domain(m) for m in res.scalars().all()]
        return Page(items=items, total=total, page=page_request.page, page_size=page_request.page_size)

    async def count_recent_by_reporter(self, reporter_id: EntityId, since: datetime) -> int:
        stmt = select(func.count()).select_from(SafetyReportModel).where(
            SafetyReportModel.reporter_id == reporter_id.value,
            SafetyReportModel.created_at >= since,
        )
        res = await self.session.execute(stmt)
        return int(res.scalar_one())

    async def similar_report_count(
        self, subject_type: SubjectType, subject_id: EntityId, excluding_report_id: EntityId
    ) -> int:
        stmt = select(func.count()).select_from(SafetyReportModel).where(
            SafetyReportModel.subject_type == subject_type.value,
            SafetyReportModel.subject_id == subject_id.value,
            SafetyReportModel.id != excluding_report_id.value,
        )
        res = await self.session.execute(stmt)
        return int(res.scalar_one())

    async def list_by_case_id(self, case_id: EntityId) -> list[Report]:
        stmt = (
            select(SafetyReportModel)
            .join(SafetyCaseReportModel, SafetyCaseReportModel.report_id == SafetyReportModel.id)
            .where(SafetyCaseReportModel.case_id == case_id.value)
        )
        res = await self.session.execute(stmt)
        return [_to_domain(m) for m in res.scalars().all()]

    async def list_unlinked(
        self, category: ReportCategory | None, page_request: PageRequest
    ) -> Page[Report]:
        subq = select(SafetyCaseReportModel.report_id)
        stmt = select(SafetyReportModel).where(SafetyReportModel.id.not_in(subq))
        if category:
            stmt = stmt.where(SafetyReportModel.category == category.value)
        
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        offset = (page_request.page - 1) * page_request.page_size
        stmt = (
            stmt.order_by(SafetyReportModel.created_at.desc())
            .offset(offset)
            .limit(page_request.page_size)
        )
        res = await self.session.execute(stmt)
        items = [_to_domain(m) for m in res.scalars().all()]
        return Page(items=items, total=total, page=page_request.page, page_size=page_request.page_size)

    async def update_status(self, report_id: EntityId, status: str) -> None:
        stmt = select(SafetyReportModel).where(SafetyReportModel.id == report_id.value)
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        if m:
            m.status = status
            await self.session.flush()

    async def count_reports_awaiting_triage(self) -> int:
        stmt = select(func.count(SafetyReportModel.id)).where(
            SafetyReportModel.status == ReportStatus.RECEIVED.value
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
